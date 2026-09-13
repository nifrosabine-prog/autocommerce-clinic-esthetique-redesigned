"""Bloc C — prescriptions médicales sécurisées."""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import ActeMedical, Patient, PrescriptionMedicale, Utilisateur
from models.episode_core import EpisodePatient, Intervention
from services.audit_medical import log_access
from services.dossier_medical import decrypt_field, encrypt_field
from services.clinical_security import require_real_role


def _role(user: dict) -> str:
    return str(user.get("role", "")).replace("RoleEnum.", "").lower()


async def _scope(db: AsyncSession, patient_id: int, user: dict, data: dict):
    clinic_id = int(user.get("clinic_id") or 0)
    if clinic_id <= 0:
        raise ValueError("Contexte clinique obligatoire")
    patient = await db.scalar(select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id, Patient.anonymized_at.is_(None)))
    if not patient:
        raise ValueError("Patient non trouvé dans cette clinique")
    episode_id = data.get("episode_id")
    if episode_id is not None:
        episode = await db.scalar(select(EpisodePatient).where(EpisodePatient.id == episode_id, EpisodePatient.patient_id == patient_id, EpisodePatient.clinic_id == clinic_id))
        if not episode:
            raise ValueError("Épisode absent ou hors clinique")
    intervention_id = data.get("intervention_id")
    if intervention_id is not None:
        intervention = await db.scalar(select(Intervention).where(Intervention.id == intervention_id, Intervention.clinic_id == clinic_id, Intervention.episode_id == episode_id))
        if not intervention:
            raise ValueError("Intervention absente ou hors périmètre")
    acte_id = data.get("acte_id")
    if acte_id is not None:
        acte = await db.scalar(select(ActeMedical).where(ActeMedical.id == acte_id, ActeMedical.clinic_id == clinic_id))
        if not acte:
            raise ValueError("Acte absent ou hors clinique")
    return clinic_id


def _serialize(item: PrescriptionMedicale) -> dict:
    return {
        "id": item.id, "patient_id": item.patient_id, "episode_id": item.episode_id,
        "consultation_id": item.consultation_id, "intervention_id": item.intervention_id, "acte_id": item.acte_id,
        "prescripteur_id": item.prescripteur_id, "date_prescription": item.date_prescription.isoformat(),
        "details": json.loads(decrypt_field(item.details_enc)), "statut": item.statut,
        "classification": item.classification, "created_at": item.created_at.isoformat(),
    }


async def create_prescription(db: AsyncSession, patient_id: int, user: dict, data: dict, meta: dict) -> dict:
    if await require_real_role(db, user, {"medecin"}) != "medecin":
        raise PermissionError("Seul un médecin peut créer une prescription")
    clinic_id = await _scope(db, patient_id, user, data)
    prescriber = await db.scalar(select(Utilisateur).where(Utilisateur.id == user["id"], Utilisateur.clinic_id == clinic_id, Utilisateur.role == "medecin", Utilisateur.is_active))
    if not prescriber:
        raise PermissionError("Prescripteur médical invalide")
    item = PrescriptionMedicale(
        clinic_id=clinic_id, patient_id=patient_id, episode_id=data.get("episode_id"),
        consultation_id=data.get("consultation_id"), intervention_id=data.get("intervention_id"), acte_id=data.get("acte_id"),
        prescripteur_id=prescriber.id, date_prescription=data.get("date_prescription") or datetime.utcnow(),
        details_enc=encrypt_field(json.dumps(data["details"], ensure_ascii=False)), statut=data.get("statut", "ACTIVE"),
    )
    db.add(item)
    await db.flush()
    await log_access(db, prescriber.id, patient_id, "CREATE_PRESCRIPTION", "prescription_medicale", item.id, clinic_id=clinic_id, ip_address=meta.get("ip_address"))
    return _serialize(item)


async def list_prescriptions(db: AsyncSession, patient_id: int, user: dict, meta: dict) -> list[dict]:
    clinic_id = await _scope(db, patient_id, user, {})
    if await require_real_role(db, user, {"medecin"}) != "medecin":
        raise PermissionError("Accès aux prescriptions réservé au médecin")
    result = await db.execute(select(PrescriptionMedicale).where(PrescriptionMedicale.patient_id == patient_id, PrescriptionMedicale.clinic_id == clinic_id).order_by(PrescriptionMedicale.date_prescription.desc()))
    await log_access(db, user["id"], patient_id, "READ_PRESCRIPTIONS", "prescription_medicale", patient_id, clinic_id=clinic_id, ip_address=meta.get("ip_address"))
    return [_serialize(item) for item in result.scalars().all()]
