"""Bloc B — antécédents, allergies, traitements et contre-indications."""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Patient, PatientMedicalFact, Utilisateur
from models.episode_core import EpisodePatient
from services.audit_medical import log_access
from services.dossier_medical import decrypt_field, encrypt_field
from services.clinical_security import require_real_role

ALLOWED_TYPES = {
    "antecedent_medical", "antecedent_chirurgical", "antecedent_anesthesique",
    "antecedent_familial", "allergie", "traitement", "contre_indication",
}


def _clinic(user: dict) -> int:
    clinic_id = int(user.get("clinic_id") or 0)
    if clinic_id <= 0:
        raise ValueError("Contexte clinique obligatoire")
    return clinic_id


async def _patient_scope(db: AsyncSession, patient_id: int, user: dict, episode_id: Optional[int] = None):
    clinic_id = _clinic(user)
    patient = await db.scalar(select(Patient).where(
        Patient.id == patient_id, Patient.clinic_id == clinic_id, Patient.anonymized_at.is_(None)
    ))
    if not patient:
        raise ValueError("Patient non trouvé dans cette clinique")
    if episode_id is not None:
        episode = await db.scalar(select(EpisodePatient).where(
            EpisodePatient.id == episode_id, EpisodePatient.patient_id == patient_id,
            EpisodePatient.clinic_id == clinic_id
        ))
        if not episode:
            raise ValueError("Épisode absent ou hors clinique")
    return clinic_id


def _read(item: PatientMedicalFact) -> dict:
    return {
        "id": item.id, "patient_id": item.patient_id, "episode_id": item.episode_id,
        "auteur_id": item.auteur_id, "type_fait": item.type_fait,
        "classification": item.classification, "source": item.source,
        "verification_status": item.verification_status, "actif": item.actif,
        "donnees": json.loads(decrypt_field(item.donnees_enc)),
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    }


async def create_fact(db: AsyncSession, patient_id: int, user: dict, data: dict, meta: dict) -> dict:
    if await require_real_role(db, user, {"medecin"}) != "medecin":
        raise PermissionError("Seul un médecin peut créer une donnée médicale structurée")
    type_fait = data.get("type_fait")
    if type_fait not in ALLOWED_TYPES:
        raise ValueError("Type de fait médical non autorisé")
    clinic_id = await _patient_scope(db, patient_id, user, data.get("episode_id"))
    author = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == user["id"], Utilisateur.clinic_id == clinic_id,
        Utilisateur.role == "medecin", Utilisateur.is_active
    ))
    if not author:
        raise PermissionError("Auteur médical invalide")
    item = PatientMedicalFact(
        clinic_id=clinic_id, patient_id=patient_id, episode_id=data.get("episode_id"),
        auteur_id=author.id, type_fait=type_fait,
        classification="MEDICAL_SENSITIVE", source=data.get("source", "MANUAL"),
        verification_status=data.get("verification_status", "VERIFIED"),
        donnees_enc=encrypt_field(json.dumps(data.get("donnees", {}), ensure_ascii=False)),
    )
    db.add(item)
    await db.flush()
    await log_access(db, author.id, patient_id, "CREATE_MEDICAL_FACT", "patient_medical_fact", item.id,
                     clinic_id=clinic_id, ip_address=meta.get("ip_address"),
                     user_agent=meta.get("user_agent"), details={"type_fait": type_fait})
    return _read(item)


async def list_facts(db: AsyncSession, patient_id: int, user: dict, meta: dict) -> list[dict]:
    clinic_id = await _patient_scope(db, patient_id, user)
    if await require_real_role(db, user, {"medecin"}) != "medecin":
        raise PermissionError("Accès aux données médicales structuré réservé au médecin")
    result = await db.execute(select(PatientMedicalFact).where(
        PatientMedicalFact.patient_id == patient_id, PatientMedicalFact.clinic_id == clinic_id,
        PatientMedicalFact.actif.is_(True)
    ).order_by(PatientMedicalFact.created_at.desc()))
    await log_access(db, user["id"], patient_id, "READ_MEDICAL_FACTS", "patient_medical_fact", patient_id,
                     clinic_id=clinic_id, ip_address=meta.get("ip_address"))
    return [_read(item) for item in result.scalars().all()]


async def soft_delete_fact(db: AsyncSession, patient_id: int, fact_id: int, user: dict, meta: dict) -> None:
    if await require_real_role(db, user, {"medecin"}) != "medecin":
        raise PermissionError("Seul un médecin peut désactiver une donnée médicale")
    clinic_id = await _patient_scope(db, patient_id, user)
    item = await db.scalar(select(PatientMedicalFact).where(
        PatientMedicalFact.id == fact_id, PatientMedicalFact.patient_id == patient_id,
        PatientMedicalFact.clinic_id == clinic_id, PatientMedicalFact.actif.is_(True)
    ))
    if not item:
        raise LookupError("Donnée médicale introuvable")
    item.actif = False
    await db.flush()
    await log_access(db, user["id"], patient_id, "SOFT_DELETE_MEDICAL_FACT", "patient_medical_fact", fact_id,
                     clinic_id=clinic_id, ip_address=meta.get("ip_address"))
