"""Bloc D — documents médicaux patients privés."""
import hashlib
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models.database import DocumentMedicalPatient, Patient
from services.audit_medical import log_access
from services.dossier_medical import decrypt_field, encrypt_field
from services.photos_clinic import _decrypt_file, _encrypt_file
from services.clinical_security import require_real_role

ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png", "text/plain"}


def _role(user: dict) -> str:
    return str(user.get("role", "")).replace("RoleEnum.", "").lower()


async def _scope(db: AsyncSession, patient_id: int, user: dict) -> int:
    clinic_id = int(user.get("clinic_id") or 0)
    patient = await db.scalar(select(Patient).where(Patient.id == patient_id, Patient.clinic_id == clinic_id, Patient.anonymized_at.is_(None)))
    if not patient:
        raise ValueError("Patient non trouvé dans cette clinique")
    if await require_real_role(db, user, {"medecin"}) != "medecin":
        raise PermissionError("Document médical réservé au médecin")
    return clinic_id


def _storage_root() -> Path:
    return Path(get_settings().uploads_dir) / "medical-documents"


async def upload_document(db: AsyncSession, patient_id: int, user: dict, file_bytes: bytes, filename: str, mime_type: str, description: str | None, consultation_id: int | None, intervention_id: int | None, meta: dict) -> dict:
    clinic_id = await _scope(db, patient_id, user)
    if mime_type not in ALLOWED_MIME:
        raise ValueError("Type de document non autorisé")
    if not file_bytes:
        raise ValueError("Document vide")
    if len(file_bytes) > 25 * 1024 * 1024:
        raise ValueError("Document trop volumineux")
    safe_name = Path(filename or "document").name[:255]
    digest = hashlib.sha256(file_bytes).hexdigest()
    relative = Path("medical-documents") / str(clinic_id) / str(patient_id) / f"{uuid4().hex}.enc"
    target = Path(get_settings().uploads_dir) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    nonce, ciphertext = _encrypt_file(file_bytes)
    target.write_bytes(nonce + ciphertext)
    item = DocumentMedicalPatient(
        clinic_id=clinic_id, patient_id=patient_id, consultation_id=consultation_id,
        intervention_id=intervention_id, importateur_id=user["id"], nom_original=safe_name,
        mime_type=mime_type, classification="EXTERNAL_MEDICAL_DOCUMENT",
        description_enc=encrypt_field(description) if description else None,
        chemin_chiffre=str(relative), hash_sha256=digest, taille_octets=len(file_bytes),
    )
    db.add(item)
    await db.flush()
    await log_access(db, user["id"], patient_id, "UPLOAD_MEDICAL_DOCUMENT", "medical_document", item.id, clinic_id=clinic_id, ip_address=meta.get("ip_address"))
    return {"id": item.id, "patient_id": patient_id, "nom_original": item.nom_original, "mime_type": item.mime_type, "classification": item.classification, "hash_sha256": item.hash_sha256, "taille_octets": item.taille_octets}


async def list_documents(db: AsyncSession, patient_id: int, user: dict, meta: dict) -> list[dict]:
    clinic_id = await _scope(db, patient_id, user)
    result = await db.execute(select(DocumentMedicalPatient).where(DocumentMedicalPatient.patient_id == patient_id, DocumentMedicalPatient.clinic_id == clinic_id, DocumentMedicalPatient.statut == "ACTIVE").order_by(DocumentMedicalPatient.created_at.desc()))
    await log_access(db, user["id"], patient_id, "READ_MEDICAL_DOCUMENTS", "medical_document", patient_id, clinic_id=clinic_id, ip_address=meta.get("ip_address"))
    return [{"id": x.id, "nom_original": x.nom_original, "mime_type": x.mime_type, "classification": x.classification, "description": decrypt_field(x.description_enc) if x.description_enc else None, "hash_sha256": x.hash_sha256, "taille_octets": x.taille_octets, "created_at": x.created_at.isoformat()} for x in result.scalars().all()]


async def read_document(db: AsyncSession, patient_id: int, document_id: int, user: dict, meta: dict) -> tuple[DocumentMedicalPatient, bytes]:
    clinic_id = await _scope(db, patient_id, user)
    item = await db.scalar(select(DocumentMedicalPatient).where(DocumentMedicalPatient.id == document_id, DocumentMedicalPatient.patient_id == patient_id, DocumentMedicalPatient.clinic_id == clinic_id, DocumentMedicalPatient.statut == "ACTIVE"))
    if not item:
        raise LookupError("Document médical introuvable")
    target = Path(get_settings().uploads_dir) / item.chemin_chiffre
    if not target.is_file():
        raise LookupError("Fichier médical indisponible")
    encrypted = target.read_bytes()
    data = _decrypt_file(encrypted[:12], encrypted[12:])
    if hashlib.sha256(data).hexdigest() != item.hash_sha256:
        raise ValueError("Intégrité du document compromise")
    await log_access(db, user["id"], patient_id, "READ_MEDICAL_DOCUMENT", "medical_document", document_id, clinic_id=clinic_id, ip_address=meta.get("ip_address"))
    return item, data


async def soft_delete_document(db: AsyncSession, patient_id: int, document_id: int, user: dict, meta: dict) -> None:
    clinic_id = await _scope(db, patient_id, user)
    item = await db.scalar(select(DocumentMedicalPatient).where(DocumentMedicalPatient.id == document_id, DocumentMedicalPatient.patient_id == patient_id, DocumentMedicalPatient.clinic_id == clinic_id, DocumentMedicalPatient.statut == "ACTIVE"))
    if not item:
        raise LookupError("Document médical introuvable")
    item.statut = "DELETED"
    item.deleted_at = datetime.utcnow()
    item.deleted_by = user["id"]
    await db.flush()
    await log_access(db, user["id"], patient_id, "SOFT_DELETE_MEDICAL_DOCUMENT", "medical_document", document_id, clinic_id=clinic_id, ip_address=meta.get("ip_address"))
