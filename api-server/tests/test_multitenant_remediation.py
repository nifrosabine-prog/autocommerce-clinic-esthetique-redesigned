from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from models.database import (
    Commission,
    LotInjectable,
    Patient,
    ProduitInjectable,
    RoleEnum,
    StatutLot,
    Utilisateur,
)
from services.commissions import list_commissions
from services.copilote_crm import CopiloteCRMService
from services.fidelite import add_points
from services.stock_injectable import get_lot_by_scan, get_stock_dashboard


@pytest.mark.asyncio
async def test_fidelite_rejects_patient_from_other_clinic(db, patient):
    other = Patient(
        clinic_id=2,
        nom="Autre",
        prenom="Clinique",
        telephone="+2222222222",
    )
    db.add(other)
    await db.flush()

    with pytest.raises(ValueError, match="Patient non trouvé"):
        await add_points(other.id, 50, "cross-tenant", db, clinic_id=1)

    refreshed = await db.scalar(select(Patient).where(Patient.id == other.id))
    assert refreshed.points_fidelite == 0


@pytest.mark.asyncio
async def test_commissions_list_excludes_other_clinic(db, medecin, patient):
    other_user = Utilisateur(
        clinic_id=2,
        email="commercial.other@example.test",
        hashed_password="x",
        nom="Autre",
        prenom="Commercial",
        role=RoleEnum.COMMERCIAL.value,
        taux_commission=Decimal("10"),
    )
    other_patient = Patient(
        clinic_id=2,
        nom="Autre",
        prenom="Patient",
        telephone="+2222222223",
    )
    db.add_all([other_user, other_patient])
    await db.flush()
    db.add(Commission(
        clinic_id=2,
        commercial_id=other_user.id,
        patient_id=other_patient.id,
        facture_id=999,
        montant_ca=Decimal("100"),
        taux_commission=Decimal("10"),
        montant_commission=Decimal("10"),
        statut="en_attente",
        periode_mois=date.today().replace(day=1),
    ))
    await db.flush()

    rows = await list_commissions(
        {"id": medecin.id, "role": RoleEnum.DIRECTRICE.value, "clinic_id": 1},
        db,
    )
    assert all(row.clinic_id == 1 for row in rows)


@pytest.mark.asyncio
async def test_stock_scan_rejects_other_clinic(db, produit):
    other_product = ProduitInjectable(
        clinic_id=2,
        nom="Produit autre",
        categorie="toxine",
        unite="unite",
        stock_minimum=Decimal("1"),
    )
    db.add(other_product)
    await db.flush()
    other_lot = LotInjectable(
        clinic_id=2,
        produit_id=other_product.id,
        numero_lot="OTHER-LOT",
        date_expiration=date.today() + timedelta(days=90),
        quantite_initiale=Decimal("10"),
        quantite_restante=Decimal("10"),
        statut=StatutLot.DISPONIBLE.value,
    )
    db.add(other_lot)
    await db.flush()

    with pytest.raises(ValueError, match="Lot non trouvé"):
        await get_lot_by_scan(
            '{"lot_id": %d}' % other_lot.id,
            db,
            clinic_id=1,
        )


@pytest.mark.asyncio
async def test_stock_dashboard_is_clinic_scoped(db, produit):
    other_product = ProduitInjectable(
        clinic_id=2,
        nom="Produit dashboard autre",
        categorie="toxine",
        unite="unite",
        stock_minimum=Decimal("1"),
    )
    db.add(other_product)
    await db.flush()
    dashboard = await get_stock_dashboard(db, clinic_id=1)
    assert all(row["produit_id"] != other_product.id for row in dashboard["produits"])


@pytest.mark.asyncio
async def test_copilote_rejects_patient_from_other_clinic(db):
    other = Patient(
        clinic_id=2,
        nom="Patient",
        prenom="Copilote",
        telephone="+2222222224",
    )
    db.add(other)
    await db.flush()
    loaded = await CopiloteCRMService._load_patient_full(db, other.id, clinic_id=1)
    assert loaded is None
