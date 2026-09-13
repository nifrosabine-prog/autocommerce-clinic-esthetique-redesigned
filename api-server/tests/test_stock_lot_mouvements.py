"""Tests — réception / crédit de stock des lots injectables + registre des mouvements.

Couvre :
- la réception crédite le lot et journalise un mouvement de type ``reception`` ;
- les refus (quantité non positive, date d'expiration passée, lot retiré) ;
- la réactivation d'un lot épuisé, et le passage en quarantaine sous le seuil ;
- l'écriture automatique d'un mouvement ``injection`` lors d'un débit.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from services.stock_injectable import register_usage, register_reception, get_recent_mouvements
from models.database import (
    LotInjectable,
    ProduitInjectable,
    StatutLot,
    TypeMouvementLot,
    MouvementLotInjectable,
)


@pytest.mark.asyncio
async def test_register_reception_credits_stock(db, lot, medecin):
    stock_avant = Decimal(str(lot.quantite_restante))
    mvt = await register_reception(
        lot_id=lot.id,
        quantite=Decimal("15.00"),
        db=db,
        utilisateur_id=medecin.id,
        motif="Nouvelle livraison",
        reference="BL-2026-0142",
    )
    await db.refresh(lot)
    assert lot.quantite_restante == stock_avant + Decimal("15.00")
    assert lot.statut == StatutLot.DISPONIBLE.value
    assert mvt.type_mouvement == TypeMouvementLot.RECEPTION.value
    assert mvt.quantite == Decimal("15.00")
    assert mvt.utilisateur_id == medecin.id
    assert mvt.reference == "BL-2026-0142"


@pytest.mark.asyncio
async def test_register_reception_rejects_non_positive_quantity(db, lot):
    with pytest.raises(ValueError, match="strictement positive"):
        await register_reception(lot_id=lot.id, quantite=Decimal("0.00"), db=db)
    with pytest.raises(ValueError, match="strictement positive"):
        await register_reception(lot_id=lot.id, quantite=Decimal("-5.00"), db=db)


@pytest.mark.asyncio
async def test_register_reception_rejects_past_expiration(db, lot):
    with pytest.raises(ValueError, match="expiration"):
        await register_reception(
            lot_id=lot.id,
            quantite=Decimal("10.00"),
            db=db,
            date_expiration=date.today() - timedelta(days=1),
        )


@pytest.mark.asyncio
async def test_register_reception_reactivates_epuise_lot(db, produit, medecin):
    epuise = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-REACTIVATE",
        date_expiration=date.today() + timedelta(days=90),
        quantite_initiale=Decimal("20.00"), quantite_restante=Decimal("0.00"),
        statut=StatutLot.EPUISE.value,
    )
    db.add(epuise)
    await db.flush()

    await register_reception(
        lot_id=epuise.id, quantite=Decimal("20.00"), db=db, utilisateur_id=medecin.id,
    )
    await db.refresh(epuise)
    assert epuise.quantite_restante == Decimal("20.00")
    assert epuise.statut == StatutLot.DISPONIBLE.value


@pytest.mark.asyncio
async def test_register_reception_sets_quarantaine_below_minimum(db, medecin):
    produit_min = ProduitInjectable(
        clinic_id=1, nom="Produit Seuil", categorie="toxine", unite="unité",
        stock_minimum=Decimal("30.00"),
    )
    db.add(produit_min)
    await db.flush()
    lot_bas = LotInjectable(
        clinic_id=1, produit_id=produit_min.id, numero_lot="LOT-SEUIL",
        date_expiration=date.today() + timedelta(days=90),
        quantite_initiale=Decimal("10.00"), quantite_restante=Decimal("10.00"),
        statut=StatutLot.QUARANTAINE.value,
    )
    db.add(lot_bas)
    await db.flush()

    await register_reception(
        lot_id=lot_bas.id, quantite=Decimal("10.00"), db=db, utilisateur_id=medecin.id,
    )
    await db.refresh(lot_bas)
    assert lot_bas.quantite_restante == Decimal("20.00")
    assert lot_bas.statut == StatutLot.QUARANTAINE.value


@pytest.mark.asyncio
async def test_register_reception_rejects_retired_lot(db, produit):
    retire = LotInjectable(
        clinic_id=1, produit_id=produit.id, numero_lot="LOT-RETIRE",
        date_expiration=date.today() + timedelta(days=90),
        quantite_initiale=Decimal("10.00"), quantite_restante=Decimal("10.00"),
        statut=StatutLot.RETIRE.value,
    )
    db.add(retire)
    await db.flush()

    with pytest.raises(ValueError, match="retiré"):
        await register_reception(lot_id=retire.id, quantite=Decimal("5.00"), db=db)


@pytest.mark.asyncio
async def test_register_usage_logs_injection_movement(db, lot, patient, medecin):
    await register_usage(
        lot_id=lot.id, dossier_id=None, patient_id=patient.id,
        praticien_id=medecin.id, quantite=Decimal("10.00"), unite="unité", db=db,
    )
    mvt = (
        await db.execute(
            select(MouvementLotInjectable)
            .where(MouvementLotInjectable.lot_id == lot.id)
            .order_by(MouvementLotInjectable.id.desc())
        )
    ).scalars().first()
    assert mvt is not None
    assert mvt.type_mouvement == TypeMouvementLot.INJECTION.value
    assert mvt.quantite == Decimal("-10.00")
    assert mvt.utilisateur_id == medecin.id


@pytest.mark.asyncio
async def test_get_recent_mouvements_returns_ledger(db, lot, medecin):
    await register_reception(lot_id=lot.id, quantite=Decimal("5.00"), db=db, utilisateur_id=medecin.id)
    mouvements = await get_recent_mouvements(db, clinic_id=1)
    assert len(mouvements) >= 1
    assert mouvements[0]["type_mouvement"] in {TypeMouvementLot.RECEPTION.value, TypeMouvementLot.INJECTION.value}
    assert mouvements[0]["produit_nom"]
    assert mouvements[0]["numero_lot"] == lot.numero_lot
