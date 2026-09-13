"""Bloc E — chronologie patient globale sans élargissement des droits."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import DocumentMedicalPatient, Patient, PatientMedicalFact, PrescriptionMedicale, ConsultationMedicale
from services.audit_medical import log_access
from services.clinical_security import require_real_role


def _role(user: dict) -> str:
    return str(user.get("role", "")).replace("RoleEnum.", "").lower()


async def get_global_timeline(db: AsyncSession, patient_id: int, user: dict, meta: dict) -> list[dict]:
    clinic_id = int(user.get("clinic_id") or 0)
    patient = await db.scalar(select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id, Patient.anonymized_at.is_(None)))
    if not patient:
        raise ValueError("Patient non trouvé dans cette clinique")
    role = _role(user)
    # Aucun endpoint médical ne doit être utilisé comme bypass : les rôles
    # non médicaux reçoivent une timeline vide, sans métadonnées révélatrices.
    if role != "medecin":
        await log_access(db, user["id"], patient_id, "READ_GLOBAL_TIMELINE_FILTERED", "patient_timeline", patient_id, clinic_id=clinic_id, ip_address=meta.get("ip_address"), details={"returned_entries": 0, "role": role})
        return []

    await require_real_role(db, user, {"medecin"})

    entries: list[dict] = []
    consultations = (await db.execute(select(ConsultationMedicale).where(ConsultationMedicale.patient_id == patient_id, ConsultationMedicale.clinic_id == clinic_id))).scalars().all()
    for item in consultations:
        entries.append({"type": "CONSULTATION", "date": item.date_consultation.isoformat(), "auteur_id": item.auteur_id, "role": "medecin", "patient_id": patient_id, "episode_id": item.episode_id, "statut": item.statut, "classification": "MEDICAL_SENSITIVE", "source_id": item.id, "summary": "Consultation médicale"})
    facts = (await db.execute(select(PatientMedicalFact).where(PatientMedicalFact.patient_id == patient_id, PatientMedicalFact.clinic_id == clinic_id, PatientMedicalFact.actif.is_(True)))).scalars().all()
    for item in facts:
        entries.append({"type": item.type_fait.upper(), "date": item.created_at.isoformat(), "auteur_id": item.auteur_id, "role": "medecin", "patient_id": patient_id, "episode_id": item.episode_id, "statut": item.verification_status, "classification": item.classification, "source_id": item.id, "summary": "Donnée médicale structurée"})
    prescriptions = (await db.execute(select(PrescriptionMedicale).where(PrescriptionMedicale.patient_id == patient_id, PrescriptionMedicale.clinic_id == clinic_id))).scalars().all()
    for item in prescriptions:
        entries.append({"type": "PRESCRIPTION", "date": item.date_prescription.isoformat(), "auteur_id": item.prescripteur_id, "role": "medecin", "patient_id": patient_id, "episode_id": item.episode_id, "statut": item.statut, "classification": item.classification, "source_id": item.id, "summary": "Prescription médicale"})
    documents = (await db.execute(select(DocumentMedicalPatient).where(DocumentMedicalPatient.patient_id == patient_id, DocumentMedicalPatient.clinic_id == clinic_id, DocumentMedicalPatient.statut == "ACTIVE"))).scalars().all()
    for item in documents:
        entries.append({"type": "DOCUMENT", "date": item.created_at.isoformat(), "auteur_id": item.importateur_id, "role": "medecin", "patient_id": patient_id, "episode_id": None, "statut": item.statut, "classification": item.classification, "source_id": item.id, "summary": "Document médical patient"})
    entries.sort(key=lambda entry: entry["date"], reverse=True)
    await log_access(db, user["id"], patient_id, "READ_GLOBAL_TIMELINE", "patient_timeline", patient_id, clinic_id=clinic_id, ip_address=meta.get("ip_address"), details={"returned_entries": len(entries), "role": role})
    return entries
