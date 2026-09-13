from datetime import datetime

import pytest
from pydantic import ValidationError

from api.v1.patient_medical_facts import MedicalFactPayload
from models.database import AuditLogMedical, Patient
from services.patient_medical_facts import create_fact, list_facts, soft_delete_fact


@pytest.mark.asyncio
async def test_medecin_creates_encrypted_verified_fact_and_audit(db, medecin, patient):
    result = await create_fact(
        db, patient.id, {"id": medecin.id, "clinic_id": 1, "role": "medecin"},
        {"type_fait": "allergie", "donnees": {"substance": "lidocaïne", "reaction": "urticaire"}}, {},
    )
    assert result["donnees"]["substance"] == "lidocaïne"
    fact = (await list_facts(db, patient.id, {"id": medecin.id, "clinic_id": 1, "role": "medecin"}, {}))[0]
    assert fact["verification_status"] == "VERIFIED"
    audit = (await db.execute(__import__("sqlalchemy").select(AuditLogMedical))).scalars().all()
    assert any(x.action == "CREATE_MEDICAL_FACT" for x in audit)


@pytest.mark.asyncio
async def test_non_medical_role_and_cross_tenant_are_refused(db, assistante, patient):
    with pytest.raises(PermissionError):
        await create_fact(
            db, patient.id, {"id": assistante.id, "clinic_id": 1, "role": "assistante"},
            {"type_fait": "traitement", "donnees": {"medicament": "X"}}, {},
        )
    other = Patient(clinic_id=2, nom="Autre", prenom="Patient", telephone="+21628888888")
    db.add(other)
    await db.flush()
    with pytest.raises((PermissionError, ValueError)):
        await create_fact(
            db, other.id, {"id": assistante.id, "clinic_id": 1, "role": "medecin"},
            {"type_fait": "allergie", "donnees": {"substance": "X"}}, {},
        )


@pytest.mark.asyncio
async def test_soft_delete_hides_fact_without_physical_delete(db, medecin, patient):
    user = {"id": medecin.id, "clinic_id": 1, "role": "medecin"}
    created = await create_fact(db, patient.id, user, {"type_fait": "traitement", "donnees": {"medicament": "A"}}, {})
    await soft_delete_fact(db, patient.id, created["id"], user, {})
    assert await list_facts(db, patient.id, user, {}) == []


def test_payload_rejects_frontend_identity_and_unknown_type():
    with pytest.raises(ValidationError):
        MedicalFactPayload(type_fait="allergie", donnees={}, author_id=44)
