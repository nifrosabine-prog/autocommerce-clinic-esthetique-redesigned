import pytest

from services.documents_medicaux import upload_document
from services.exports_patient import export_structured
from services.patient_medical_facts import create_fact
from services.prescriptions_medicales import create_prescription
from services.timeline_patient_global import get_global_timeline


@pytest.mark.asyncio
async def test_forged_medical_roles_are_rejected_against_real_user(db, assistante, patient):
    forged = {"id": assistante.id, "clinic_id": 1, "role": "medecin"}
    calls = [
        lambda: create_fact(db, patient.id, forged, {"type_fait": "allergie", "donnees": {"substance": "X"}}, {}),
        lambda: create_prescription(db, patient.id, forged, {"details": {"medicament": "X"}}, {}),
        lambda: upload_document(db, patient.id, forged, b"x", "x.pdf", "application/pdf", None, None, None, {}),
        lambda: export_structured(db, patient.id, forged, {}),
        lambda: get_global_timeline(db, patient.id, forged, {}),
    ]
    for call in calls:
        with pytest.raises(PermissionError):
            await call()


@pytest.mark.asyncio
async def test_cross_tenant_idor_never_returns_patient_data(db, medecin, patient):
    other_user = {"id": medecin.id, "clinic_id": 1, "role": "medecin"}
    from models.database import Patient
    other = Patient(clinic_id=2, nom="Tenant", prenom="Autre", telephone="+21624444444")
    db.add(other)
    await db.flush()
    for call in (
        lambda: get_global_timeline(db, other.id, other_user, {}),
        lambda: export_structured(db, other.id, other_user, {}),
        lambda: create_fact(db, other.id, other_user, {"type_fait": "allergie", "donnees": {"substance": "X"}}, {}),
        lambda: create_prescription(db, other.id, other_user, {"details": {"medicament": "X"}}, {}),
        lambda: upload_document(db, other.id, other_user, b"x", "x.pdf", "application/pdf", None, None, None, {}),
    ):
        with pytest.raises(ValueError):
            await call()
