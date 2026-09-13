"""Bloc G — consultation contrôlée des traces d'audit médical."""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import AuditLogMedical, Utilisateur

ALLOWED_AUDIT_ROLES = {"medecin", "directrice", "admin", "super_admin"}


async def query_medical_audit(db: AsyncSession, user: dict, patient_id: Optional[int] = None, action: Optional[str] = None, limit: int = 100, offset: int = 0) -> list[dict]:
    role = str(user.get("role", "")).replace("RoleEnum.", "").lower()
    authenticated = await db.scalar(select(Utilisateur).where(Utilisateur.id == user.get("id"), Utilisateur.clinic_id == user.get("clinic_id"), Utilisateur.is_active))
    if not authenticated or role not in ALLOWED_AUDIT_ROLES or str(authenticated.role).replace("RoleEnum.", "").lower() != role:
        raise PermissionError("Accès aux traces médicales non autorisé")
    clinic_id = int(user.get("clinic_id") or 0)
    query = select(AuditLogMedical).where(AuditLogMedical.clinic_id == clinic_id)
    if patient_id is not None:
        query = query.where(AuditLogMedical.patient_id == patient_id)
    if action:
        query = query.where(AuditLogMedical.action == action)
    query = query.order_by(AuditLogMedical.created_at.desc()).offset(offset).limit(min(limit, 500))
    result = await db.execute(query)
    return [{
        "id": row.id, "clinic_id": row.clinic_id, "utilisateur_id": row.utilisateur_id,
        "patient_id": row.patient_id, "action": row.action, "resource_type": row.resource_type,
        "resource_id": row.resource_id, "ip_address": row.ip_address,
        "created_at": row.created_at.isoformat(), "details": row.details or {},
    } for row in result.scalars().all()]
