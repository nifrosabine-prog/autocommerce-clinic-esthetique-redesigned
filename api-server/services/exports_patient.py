"""Bloc F — exports structurés et PDF du dossier patient."""
import io
import json
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy.ext.asyncio import AsyncSession

from services.audit_medical import log_access
from services.timeline_patient_global import get_global_timeline
from services.clinical_security import require_real_role


def _role(user: dict) -> str:
    return str(user.get("role", "")).replace("RoleEnum.", "").lower()


async def export_structured(db: AsyncSession, patient_id: int, user: dict, meta: dict) -> dict:
    if await require_real_role(db, user, {"medecin"}) != "medecin":
        raise PermissionError("Export médical réservé au médecin")
    entries = await get_global_timeline(db, patient_id, user, meta)
    payload = {
        "format": "clinical-core.patient-export.v1",
        "exported_at": datetime.utcnow().isoformat(),
        "patient_id": patient_id,
        "classification": "MEDICAL_SENSITIVE",
        "entries": entries,
    }
    await log_access(db, user["id"], patient_id, "EXPORT_STRUCTURED", "patient_export", patient_id, clinic_id=user["clinic_id"], ip_address=meta.get("ip_address"), details={"entries": len(entries), "format": "json"})
    return payload


async def export_pdf(db: AsyncSession, patient_id: int, user: dict, meta: dict) -> bytes:
    payload = await export_structured(db, patient_id, user, meta)
    styles = getSampleStyleSheet()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = [Paragraph("Dossier patient — export clinique", styles["Title"]), Spacer(1, 0.3 * cm), Paragraph(f"Patient : {patient_id}", styles["Normal"]), Paragraph(f"Export : {payload['exported_at']}", styles["Normal"]), Paragraph("Confidentiel — données médicales sensibles", styles["Normal"]), Spacer(1, 0.5 * cm)]
    for entry in payload["entries"]:
        safe = f"{entry['type']} — {entry['date']} — statut : {entry['statut']} — source : {entry['source_id']}"
        story.append(Paragraph(safe, styles["BodyText"]))
        story.append(Spacer(1, 0.15 * cm))
    doc.build(story)
    await log_access(db, user["id"], patient_id, "EXPORT_PDF", "patient_export", patient_id, clinic_id=user["clinic_id"], ip_address=meta.get("ip_address"), details={"entries": len(payload["entries"]), "format": "pdf"})
    return buffer.getvalue()
