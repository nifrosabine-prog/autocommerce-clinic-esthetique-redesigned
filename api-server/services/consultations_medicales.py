"""Services du Bloc A — consultation médicale structurée."""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import ConsultationMedicale, Patient, RendezVous, Utilisateur
from models.episode_core import EpisodePatient
from services.audit_medical import log_access
from services.dossier_medical import decrypt_field, encrypt_field

ENCRYPTED_FIELDS = (
    "motif", "demande_patient", "objectif", "histoire", "evolution",
    "traitements_precedents", "contexte", "observations_cliniques", "mesures",
    "diagnostic", "indication", "contre_indications", "facteurs_risque",
    "objectifs_therapeutiques", "benefices_attendus", "risques", "alternatives",
    "plan_therapeutique", "recommandation", "acte_propose", "suivi",
)


def _clinic_id(user: dict) -> int:
    clinic_id = user.get("clinic_id")
    if not clinic_id or clinic_id <= 0:
        raise ValueError("Contexte clinique obligatoire")
    return int(clinic_id)


async def _scope_context(db: AsyncSession, patient_id: int, user: dict, episode_id: Optional[int], rdv_id: Optional[int]):
    clinic_id = _clinic_id(user)
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
    if rdv_id is not None:
        rdv = await db.scalar(select(RendezVous).where(
            RendezVous.id == rdv_id, RendezVous.patient_id == patient_id,
            RendezVous.clinic_id == clinic_id
        ))
        if not rdv:
            raise ValueError("Rendez-vous absent ou hors clinique")
    return clinic_id


def _serialize(item: ConsultationMedicale, include_sensitive: bool = True) -> dict:
    out = {
        "id": item.id, "patient_id": item.patient_id, "episode_id": item.episode_id,
        "rdv_id": item.rdv_id, "auteur_id": item.auteur_id,
        "date_consultation": item.date_consultation.isoformat(),
        "type_consultation": item.type_consultation, "statut": item.statut,
        "prochain_rdv_at": item.prochain_rdv_at.isoformat() if item.prochain_rdv_at else None,
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    }
    for field in ENCRYPTED_FIELDS:
        encrypted = getattr(item, f"{field}_enc")
        out[field] = decrypt_field(encrypted) if include_sensitive and encrypted else None
    return out


async def create_consultation(db: AsyncSession, patient_id: int, user: dict, data: dict, request_meta: dict) -> ConsultationMedicale:
    if user.get("role") != "medecin":
        raise PermissionError("Seul un médecin peut créer une consultation médicale")
    clinic_id = await _scope_context(db, patient_id, user, data.get("episode_id"), data.get("rdv_id"))
    author = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == user["id"], Utilisateur.clinic_id == clinic_id,
        Utilisateur.role == "medecin", Utilisateur.is_active
    ))
    if not author:
        raise PermissionError("Auteur médical invalide")
    item = ConsultationMedicale(
        clinic_id=clinic_id, patient_id=patient_id, episode_id=data.get("episode_id"),
        rdv_id=data.get("rdv_id"), auteur_id=author.id,
        date_consultation=data["date_consultation"],
        type_consultation=data.get("type_consultation", "initiale"),
        prochain_rdv_at=data.get("prochain_rdv_at"), statut=data.get("statut", "brouillon"),
    )
    for field in ENCRYPTED_FIELDS:
        value = data.get(field)
        setattr(item, f"{field}_enc", encrypt_field(value) if value else None)
    db.add(item)
    await db.flush()
    await log_access(db, author.id, patient_id, "CREATE_CONSULTATION", "consultation_medicale", item.id,
                     clinic_id=clinic_id, ip_address=request_meta.get("ip_address"),
                     user_agent=request_meta.get("user_agent"), details={"episode_id": item.episode_id})
    return item


async def get_consultation(db: AsyncSession, consultation_id: int, patient_id: int, user: dict, request_meta: dict) -> dict:
    clinic_id = await _scope_context(db, patient_id, user, None, None)
    item = await db.scalar(select(ConsultationMedicale).where(
        ConsultationMedicale.id == consultation_id, ConsultationMedicale.patient_id == patient_id,
        ConsultationMedicale.clinic_id == clinic_id
    ))
    if not item:
        raise LookupError("Consultation introuvable")
    if user.get("role") != "medecin":
        raise PermissionError("Accès médical réservé au médecin")
    await log_access(db, user["id"], patient_id, "READ_CONSULTATION", "consultation_medicale", item.id,
                     clinic_id=clinic_id, ip_address=request_meta.get("ip_address"))
    return _serialize(item)


async def list_consultations(db: AsyncSession, patient_id: int, user: dict, request_meta: dict) -> list[dict]:
    clinic_id = await _scope_context(db, patient_id, user, None, None)
    if user.get("role") != "medecin":
        raise PermissionError("Accès médical réservé au médecin")
    result = await db.execute(select(ConsultationMedicale).where(
        ConsultationMedicale.patient_id == patient_id, ConsultationMedicale.clinic_id == clinic_id
    ).order_by(ConsultationMedicale.date_consultation.desc()))
    await log_access(db, user["id"], patient_id, "READ_CONSULTATIONS", "consultation_medicale", patient_id,
                     clinic_id=clinic_id, ip_address=request_meta.get("ip_address"))
    return [_serialize(item) for item in result.scalars().all()]


async def update_consultation(db: AsyncSession, consultation_id: int, patient_id: int, user: dict, data: dict, request_meta: dict) -> dict:
    if user.get("role") != "medecin":
        raise PermissionError("Seul un médecin peut modifier une consultation médicale")
    clinic_id = _clinic_id(user)
    item = await db.scalar(select(ConsultationMedicale).where(
        ConsultationMedicale.id == consultation_id, ConsultationMedicale.patient_id == patient_id,
        ConsultationMedicale.clinic_id == clinic_id
    ))
    if not item:
        raise LookupError("Consultation introuvable")
    for field in ENCRYPTED_FIELDS:
        if field in data:
            setattr(item, f"{field}_enc", encrypt_field(data[field]) if data[field] else None)
    for field in ("type_consultation", "statut", "date_consultation", "prochain_rdv_at"):
        if field in data:
            setattr(item, field, data[field])
    await db.flush()
    await log_access(db, user["id"], patient_id, "UPDATE_CONSULTATION", "consultation_medicale", item.id,
                     clinic_id=clinic_id, ip_address=request_meta.get("ip_address"))
    return _serialize(item)
