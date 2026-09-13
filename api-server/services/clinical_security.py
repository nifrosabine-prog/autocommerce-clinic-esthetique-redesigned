"""Guards communs de sécurité clinique — identité backend et rôle réel."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Utilisateur


async def require_real_role(db: AsyncSession, user: dict, allowed: set[str]) -> str:
    role = str(user.get("role", "")).replace("RoleEnum.", "").lower()
    user_id = user.get("id")
    clinic_id = user.get("clinic_id")
    authenticated = await db.scalar(select(Utilisateur).where(Utilisateur.id == user_id, Utilisateur.clinic_id == clinic_id, Utilisateur.is_active))
    actual = str(authenticated.role).replace("RoleEnum.", "").lower() if authenticated else ""
    if not authenticated or actual != role or actual not in allowed:
        raise PermissionError("Identité ou rôle clinique non autorisé")
    return actual
