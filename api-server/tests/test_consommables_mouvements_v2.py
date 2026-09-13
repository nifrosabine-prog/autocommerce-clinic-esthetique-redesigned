"""Tests — mouvements consommables v2 : ajustement d'inventaire, verrou, historique."""
from decimal import Decimal

import pytest

from services.consommables import ConsommableService
from models.database import Consommable


def _make_consommable(stock: str = "10.00") -> Consommable:
    return Consommable(
        clinic_id=1, nom="Gants Latex", categorie="Hygiène", unite="boite",
        stock_actuel=Decimal(stock), seuil_alerte=Decimal("5.00"),
        stock_minimum=Decimal("2.00"), prix_unitaire=Decimal("0.000"),
    )


@pytest.mark.asyncio
async def test_entree_credits_stock(db, medecin):
    c = _make_consommable()
    db.add(c)
    await db.flush()

    await ConsommableService.add_mouvement(db, c.id, "entree", 5.0, medecin.id, motif="Réception commande")
    await db.refresh(c)
    assert c.stock_actuel == Decimal("15.00")


@pytest.mark.asyncio
async def test_sortie_refuses_insufficient_stock(db, medecin):
    c = _make_consommable("3.00")
    db.add(c)
    await db.flush()

    with pytest.raises(ValueError, match="[Ss]tock insuffisant"):
        await ConsommableService.add_mouvement(db, c.id, "sortie", 5.0, medecin.id, motif="Utilisation soin")


@pytest.mark.asyncio
async def test_ajustement_replaces_stock(db, medecin):
    c = _make_consommable("10.00")
    db.add(c)
    await db.flush()

    mvt = await ConsommableService.add_mouvement(
        db, c.id, "ajustement", 4.0, medecin.id, motif="Inventaire mensuel"
    )
    await db.refresh(c)
    assert c.stock_actuel == Decimal("4.00")
    assert mvt.type == "ajustement"
    assert mvt.quantite == Decimal("4.00")


@pytest.mark.asyncio
async def test_ajustement_requires_motif(db, medecin):
    c = _make_consommable()
    db.add(c)
    await db.flush()

    with pytest.raises(ValueError, match="motif"):
        await ConsommableService.add_mouvement(db, c.id, "ajustement", 5.0, medecin.id)


@pytest.mark.asyncio
async def test_entree_rejects_non_positive(db, medecin):
    c = _make_consommable()
    db.add(c)
    await db.flush()

    with pytest.raises(ValueError, match="strictement positive"):
        await ConsommableService.add_mouvement(db, c.id, "entree", 0.0, medecin.id)


@pytest.mark.asyncio
async def test_get_mouvements_history(db, medecin):
    c = _make_consommable()
    db.add(c)
    await db.flush()

    await ConsommableService.add_mouvement(db, c.id, "entree", 5.0, medecin.id, motif="Réception")
    await ConsommableService.add_mouvement(db, c.id, "sortie", 2.0, medecin.id, motif="Soin A")
    history = await ConsommableService.get_mouvements(db, c.id)
    assert len(history) == 2
    assert history[0]["type"] == "sortie"  # plus récent en premier
    assert history[0]["quantite"] == 2.0

    recent = await ConsommableService.get_recent_mouvements(db)
    assert any(m["consommable_id"] == c.id for m in recent)
