import inspect

import pytest
from sqlalchemy import select

from models.database import AuditLogMedical, Patient
from services import audit_medical
from services.audit_medical import log_access
from services.audit_medical_query import query_medical_audit


@pytest.mark.asyncio
async def test_authorized_audit_query_is_clinic_scoped_and_append_only(db, medecin, patient):
    await log_access(db, medecin.id, patient.id, "READ_TEST", "patient", patient.id, clinic_id=1, details={"safe": True})
    entries = await query_medical_audit(db, {"id": medecin.id, "clinic_id": 1, "role": "medecin"}, patient.id)
    assert entries[0]["action"] == "READ_TEST"
    assert entries[0]["details"] == {"safe": True}
    names = [name for name, _ in inspect.getmembers(audit_medical, inspect.isfunction)]
    assert "update_audit" not in names
    assert "delete_audit" not in names


@pytest.mark.asyncio
async def test_unauthorized_role_and_other_clinic_cannot_read_audit(db, assistante, medecin, patient):
    await log_access(db, assistante.id, patient.id, "READ_TEST", "patient", patient.id, clinic_id=1)
    with pytest.raises(PermissionError):
        await query_medical_audit(db, {"id": assistante.id, "clinic_id": 1, "role": "assistante"}, patient.id)
    other = Patient(clinic_id=2, nom="Autre", prenom="Clinique", telephone="+21625555555")
    db.add(other)
    await db.flush()
    # Un médecin de clinique 1 ne peut pas découvrir les traces de la clinique 2.
    assert await query_medical_audit(db, {"id": medecin.id, "clinic_id": 1, "role": "medecin"}, other.id) == []
