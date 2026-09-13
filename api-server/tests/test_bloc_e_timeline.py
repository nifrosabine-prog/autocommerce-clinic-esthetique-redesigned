from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from models.database import AuditLogMedical
from services.patient_medical_facts import create_fact
from services.prescriptions_medicales import create_prescription
from services.timeline_patient_global import get_global_timeline


@pytest.mark.asyncio
async def test_medecin_global_timeline_aggregates_without_duplicate_storage(db, medecin, patient):
    user = {"id": medecin.id, "clinic_id": 1, "role": "medecin"}
    await create_fact(db, patient.id, user, {"type_fait": "allergie", "donnees": {"substance": "X"}}, {})
    await create_prescription(db, patient.id, user, {"date_prescription": datetime.utcnow(), "details": {"medicament": "Y"}}, {})
    timeline = await get_global_timeline(db, patient.id, user, {})
    assert {x["type"] for x in timeline} >= {"ALLERGIE", "PRESCRIPTION"}
    assert timeline == sorted(timeline, key=lambda x: x["date"], reverse=True)
    assert all(x["patient_id"] == patient.id for x in timeline)
    audits = (await db.execute(select(AuditLogMedical))).scalars().all()
    assert any(x.action == "READ_GLOBAL_TIMELINE" for x in audits)


@pytest.mark.asyncio
async def test_non_medical_timeline_returns_no_metadata_orbidden_entries(db, assistante, patient):
    timeline = await get_global_timeline(db, patient.id, {"id": assistante.id, "clinic_id": 1, "role": "assistante"}, {})
    assert timeline == []
