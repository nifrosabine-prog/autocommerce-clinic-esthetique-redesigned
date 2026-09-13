from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from api.v1.prescriptions_medicales import PrescriptionPayload
from models.database import AuditLogMedical, Patient
from services.prescriptions_medicales import create_prescription, list_prescriptions


@pytest.mark.asyncio
async def test_medecin_creates_encrypted_prescription_and_audit(db, medecin, patient):
    user = {"id": medecin.id, "clinic_id": 1, "role": "medecin"}
    result = await create_prescription(db, patient.id, user, {
        "date_prescription": datetime(2026, 9, 10, 11, 0),
        "details": {"medicament": "Produit médical", "dosage": "10 mg", "frequence": "1/jour", "duree": "7 jours"},
    }, {})
    assert result["prescripteur_id"] == medecin.id
    assert result["details"]["dosage"] == "10 mg"
    row = (await db.execute(select(AuditLogMedical))).scalars().all()
    assert any(x.action == "CREATE_PRESCRIPTION" for x in row)
    assert (await list_prescriptions(db, patient.id, user, {}))[0]["prescripteur_id"] == medecin.id


@pytest.mark.asyncio
async def test_non_medical_and_cross_tenant_prescribing_are_refused(db, assistante, patient):
    with pytest.raises(PermissionError):
        await create_prescription(db, patient.id, {"id": assistante.id, "clinic_id": 1, "role": "assistante"}, {"details": {"medicament": "X"}}, {})
    other = Patient(clinic_id=2, nom="Autre", prenom="Patient", telephone="+21627777777")
    db.add(other)
    await db.flush()
    with pytest.raises((PermissionError, ValueError)):
        await create_prescription(db, other.id, {"id": assistante.id, "clinic_id": 1, "role": "medecin"}, {"details": {"medicament": "X"}}, {})


def test_frontend_cannot_supply_prescriber_identity():
    with pytest.raises(ValidationError):
        PrescriptionPayload(details={"medicament": "X"}, prescripteur_id=999)
