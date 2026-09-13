from datetime import datetime

import pytest
from sqlalchemy import select

from models.database import AuditLogMedical
from services.exports_patient import export_pdf, export_structured
from services.patient_medical_facts import create_fact


@pytest.mark.asyncio
async def test_medecin_exports_structured_and_pdf_with_audit(db, medecin, patient):
    user = {"id": medecin.id, "clinic_id": 1, "role": "medecin"}
    await create_fact(db, patient.id, user, {"type_fait": "allergie", "donnees": {"substance": "X"}}, {})
    structured = await export_structured(db, patient.id, user, {})
    assert structured["format"] == "clinical-core.patient-export.v1"
    assert any(entry["type"] == "ALLERGIE" for entry in structured["entries"])
    pdf = await export_pdf(db, patient.id, user, {})
    assert pdf.startswith(b"%PDF")
    audits = (await db.execute(select(AuditLogMedical))).scalars().all()
    assert any(x.action == "EXPORT_STRUCTURED" for x in audits)
    assert any(x.action == "EXPORT_PDF" for x in audits)


@pytest.mark.asyncio
async def test_non_medical_export_is_denied(db, assistante, patient):
    with pytest.raises(PermissionError):
        await export_structured(db, patient.id, {"id": assistante.id, "clinic_id": 1, "role": "assistante"}, {})
    with pytest.raises(PermissionError):
        await export_pdf(db, patient.id, {"id": assistante.id, "clinic_id": 1, "role": "assistante"}, {})
