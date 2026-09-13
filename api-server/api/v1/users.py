"""Gestion sécurisée des comptes de l'équipe clinique."""

from datetime import date
from io import StringIO
from typing import Optional
import csv
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_db
from middleware.auth import get_password_hash
from middleware.clinic_rbac import require_role
from models.database import AuditLogTeam, RoleEnum, Utilisateur


router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)

MANAGE_ROLES = (RoleEnum.DIRECTRICE, RoleEnum.ADMIN)
CLINIC_ASSIGNABLE_ROLES = {
    RoleEnum.DIRECTRICE,
    RoleEnum.MEDECIN,
    RoleEnum.ESTHETICIENNE,
    RoleEnum.ASSISTANTE,
    RoleEnum.COMMERCIAL,
    RoleEnum.PRESTATAIRE,
}


def _validate_clinic_assignable_role(role: Optional[RoleEnum]) -> None:
    """A clinic administrator must never mint a platform-global role."""
    if role is None:
        return
    if role not in CLINIC_ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le rôle demandé ne peut pas être attribué depuis une clinique",
        )


LEADERSHIP_ROLES = (RoleEnum.DIRECTRICE, RoleEnum.ADMIN)


def _role_value(role: RoleEnum | str) -> str:
    return role.value if isinstance(role, RoleEnum) else str(role)


def _user_audit_snapshot(user: Utilisateur) -> dict:
    """Capture les changements métier sans jamais journaliser le mot de passe."""
    return {
        "id": user.id,
        "email": user.email,
        "nom": user.nom,
        "prenom": user.prenom,
        "role": _role_value(user.role),
        "telephone": user.telephone,
        "specialite": user.specialite,
        "adresse": user.adresse,
        "date_embauche": user.date_embauche.isoformat() if user.date_embauche else None,
        "is_active": user.is_active,
        "is_public": user.is_public,
    }


async def _ensure_not_last_active_leader(
    db: AsyncSession,
    user: Utilisateur,
    *,
    replacement_role: RoleEnum | str | None = None,
) -> None:
    """Keep one active account for each clinic leadership role.

    This deliberately follows the product acceptance rule: a clinic cannot
    remove its last active directrice, nor its last active admin.
    """
    current_role = _role_value(user.role)
    leader_values = {_role_value(role) for role in LEADERSHIP_ROLES}
    next_role = _role_value(replacement_role) if replacement_role is not None else current_role
    if not user.is_active or current_role not in leader_values or next_role == current_role:
        return

    active_count = await db.scalar(
        select(func.count(Utilisateur.id)).where(
            Utilisateur.clinic_id == user.clinic_id,
            Utilisateur.role == current_role,
            Utilisateur.is_active.is_(True),
        )
    )
    if (active_count or 0) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de retirer le dernier compte {current_role} actif de la clinique",
        )


async def _ensure_not_last_active_leader_before_deactivation(
    db: AsyncSession,
    user: Utilisateur,
    becoming_inactive: bool,
) -> None:
    if not becoming_inactive:
        return
    current_role = _role_value(user.role)
    if not user.is_active or current_role not in {_role_value(role) for role in LEADERSHIP_ROLES}:
        return
    active_count = await db.scalar(
        select(func.count(Utilisateur.id)).where(
            Utilisateur.clinic_id == user.clinic_id,
            Utilisateur.role == current_role,
            Utilisateur.is_active.is_(True),
        )
    )
    if (active_count or 0) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Impossible de désactiver le dernier compte {current_role} actif de la clinique",
        )


class UserCreate(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=128)
    role: RoleEnum
    telephone: Optional[str] = Field(default=None, max_length=20)
    specialite: Optional[str] = Field(default=None, max_length=100)
    adresse: Optional[str] = Field(default=None, max_length=500)
    date_embauche: Optional[date] = None
    diplomes: Optional[list[str]] = Field(default=None, max_length=30)
    certifications: Optional[list[str]] = Field(default=None, max_length=30)
    documents_professionnels: Optional[list[str]] = Field(default=None, max_length=30)
    notes_internes: Optional[str] = Field(default=None, max_length=5000)
    agenda_color: Optional[str] = Field(default=None, max_length=7)
    is_public: bool = True
    acte_ids: Optional[list[int]] = None


class UserUpdate(BaseModel):
    email: Optional[str] = Field(default=None, min_length=5, max_length=255)
    nom: Optional[str] = Field(default=None, min_length=1, max_length=100)
    prenom: Optional[str] = Field(default=None, min_length=1, max_length=100)
    password: Optional[str] = Field(default=None, min_length=12, max_length=128)
    role: Optional[RoleEnum] = None
    telephone: Optional[str] = Field(default=None, max_length=20)
    specialite: Optional[str] = Field(default=None, max_length=100)
    adresse: Optional[str] = Field(default=None, max_length=500)
    date_embauche: Optional[date] = None
    diplomes: Optional[list[str]] = Field(default=None, max_length=30)
    certifications: Optional[list[str]] = Field(default=None, max_length=30)
    documents_professionnels: Optional[list[str]] = Field(default=None, max_length=30)
    notes_internes: Optional[str] = Field(default=None, max_length=5000)
    agenda_color: Optional[str] = Field(default=None, max_length=7)
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    acte_ids: Optional[list[int]] = None


class UserOut(BaseModel):
    id: int
    email: str
    nom: str
    prenom: str
    role: str
    telephone: Optional[str] = None
    specialite: Optional[str] = None
    adresse: Optional[str] = None
    date_embauche: Optional[date] = None
    diplomes: list[str] = []
    certifications: list[str] = []
    documents_professionnels: list[str] = []
    notes_internes: Optional[str] = None
    agenda_color: Optional[str] = None
    is_active: bool
    is_public: bool
    acte_ids: list[int] = []

    class Config:
        from_attributes = True


def _serialize_user(user: Utilisateur) -> dict:
    # Ne jamais déclencher de lazy-load depuis un endpoint async. Les routes de
    # lecture chargent explicitement actes_pratiques avec selectinload ; pour un
    # objet nouvellement créé, l'absence de relation chargée signifie simplement
    # qu'il n'a encore aucun acte associé.
    loaded_actes = user.__dict__.get("actes_pratiques") or []
    return {
        "id": user.id,
        "email": user.email,
        "nom": user.nom,
        "prenom": user.prenom,
        "role": user.role.value if isinstance(user.role, RoleEnum) else str(user.role),
        "telephone": user.telephone,
        "specialite": user.specialite,
        "adresse": user.adresse,
        "date_embauche": user.date_embauche,
        "diplomes": user.diplomes or [],
        "certifications": user.certifications or [],
        "documents_professionnels": user.documents_professionnels or [],
        "notes_internes": user.notes_internes,
        "agenda_color": user.agenda_color,
        "is_active": user.is_active,
        "is_public": user.is_public,
        "acte_ids": [a.id for a in loaded_actes],
    }


@router.get("", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Utilisateur)
        .options(selectinload(Utilisateur.actes_pratiques))
        .where(Utilisateur.clinic_id == current_user["clinic_id"])
        .order_by(Utilisateur.nom, Utilisateur.prenom)
    )
    return [_serialize_user(user) for user in result.scalars().all()]


@router.get("/export.csv")
async def export_users_csv(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    """Exporte les membres de la clinique dans un CSV compatible Excel."""
    result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.clinic_id == current_user["clinic_id"])
        .order_by(Utilisateur.nom, Utilisateur.prenom)
    )
    users = result.scalars().all()

    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow([
        "ID", "Nom", "Prénom", "Email", "Rôle", "Téléphone", "Spécialité",
        "Adresse", "Date d'embauche", "Diplômes", "Certifications",
        "Documents professionnels", "Notes internes", "Couleur agenda", "Statut",
    ])
    for user in users:
        writer.writerow([
            user.id,
            user.nom,
            user.prenom,
            user.email,
            user.role.value if isinstance(user.role, RoleEnum) else str(user.role),
            user.telephone or "",
            user.specialite or "",
            user.adresse or "",
            user.date_embauche.isoformat() if user.date_embauche else "",
            "; ".join(user.diplomes or []),
            "; ".join(user.certifications or []),
            "; ".join(user.documents_professionnels or []),
            user.notes_internes or "",
            user.agenda_color or "",
            "Actif" if user.is_active else "Inactif",
        ])

    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="equipe.csv"'},
    )


@router.get("/audit-logs")
async def list_team_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    """Historique des actions de gestion d'équipe, limité à la clinique."""
    from sqlalchemy.orm import joinedload

    result = await db.execute(
        select(AuditLogTeam)
        .where(AuditLogTeam.clinic_id == current_user["clinic_id"])
        .options(joinedload(AuditLogTeam.modifie_par))
        .order_by(AuditLogTeam.created_at.desc())
        .limit(100)
    )
    return [
        {
            "id": log.id,
            "utilisateur_id": log.utilisateur_id,
            "action": log.action,
            "valeur_avant": log.valeur_avant,
            "valeur_apres": log.valeur_apres,
            "modifie_par_id": log.modifie_par_id,
            "modifie_par_nom": (
                f"{log.modifie_par.prenom} {log.modifie_par.nom}"
                if log.modifie_par else None
            ),
            "created_at": log.created_at,
        }
        for log in result.scalars().all()
    ]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    _validate_clinic_assignable_role(payload.role)
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=422, detail="Adresse email invalide")

    existing = await db.execute(select(Utilisateur).where(Utilisateur.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cet email")

    user = Utilisateur(
        clinic_id=current_user["clinic_id"],
        email=email,
        nom=payload.nom.strip(),
        prenom=payload.prenom.strip(),
        hashed_password=get_password_hash(payload.password),
        role=payload.role.value,
        telephone=payload.telephone,
        specialite=payload.specialite,
        adresse=payload.adresse,
        date_embauche=payload.date_embauche,
        diplomes=payload.diplomes,
        certifications=payload.certifications,
        documents_professionnels=payload.documents_professionnels,
        notes_internes=payload.notes_internes,
        agenda_color=payload.agenda_color,
        is_public=payload.is_public,
        is_active=True,
        mfa_enabled=False,
        mfa_failed_attempts=0,
    )
    
    if payload.acte_ids:
        from models.database import ActeMedical
        res_actes = await db.execute(
            select(ActeMedical).where(
                ActeMedical.id.in_(payload.acte_ids),
                ActeMedical.clinic_id == current_user["clinic_id"]
            )
        )
        user.actes_pratiques = list(res_actes.scalars().all())

    db.add(user)
    try:
        await db.flush()
        db.add(AuditLogTeam(
            clinic_id=current_user["clinic_id"],
            utilisateur_id=user.id,
            action="creation",
            valeur_avant=None,
            valeur_apres=_user_audit_snapshot(user),
            modifie_par_id=current_user["id"],
        ))
        await db.commit()
        result = await db.execute(
            select(Utilisateur)
            .options(selectinload(Utilisateur.actes_pratiques))
            .where(Utilisateur.id == user.id)
        )
        user = result.scalar_one()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Impossible de créer ce compte") from exc
    return _serialize_user(user)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Utilisateur)
        .options(selectinload(Utilisateur.actes_pratiques))
        .where(
            Utilisateur.id == user_id,
            Utilisateur.clinic_id == current_user["clinic_id"],
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    return _serialize_user(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    started_at = time.perf_counter()
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Utilisateur)
        .options(selectinload(Utilisateur.actes_pratiques))
        .where(
            Utilisateur.id == user_id,
            Utilisateur.clinic_id == current_user["clinic_id"],
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Compte introuvable")

    _validate_clinic_assignable_role(payload.role)
    before = _user_audit_snapshot(user)
    await _ensure_not_last_active_leader_before_deactivation(
        db, user, payload.is_active is False
    )
    await _ensure_not_last_active_leader(
        db, user, replacement_role=payload.role
    )
    if payload.email is not None:
        user.email = payload.email.strip().lower()
    if payload.nom is not None:
        user.nom = payload.nom.strip()
    if payload.prenom is not None:
        user.prenom = payload.prenom.strip()
    if payload.password is not None:
        user.hashed_password = get_password_hash(payload.password)
    if payload.role is not None:
        user.role = payload.role.value
    if payload.telephone is not None:
        user.telephone = payload.telephone
    if payload.specialite is not None:
        user.specialite = payload.specialite
    if payload.adresse is not None:
        user.adresse = payload.adresse
    if payload.date_embauche is not None:
        user.date_embauche = payload.date_embauche
    if payload.diplomes is not None:
        user.diplomes = payload.diplomes
    if payload.certifications is not None:
        user.certifications = payload.certifications
    if payload.documents_professionnels is not None:
        user.documents_professionnels = payload.documents_professionnels
    if payload.notes_internes is not None:
        user.notes_internes = payload.notes_internes
    if payload.agenda_color is not None:
        user.agenda_color = payload.agenda_color
    if payload.is_active is not None:
        if user.id == current_user["id"] and not payload.is_active:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte")
        user.is_active = payload.is_active
    if payload.is_public is not None:
        user.is_public = payload.is_public
    
    if payload.acte_ids is not None:
        from models.database import ActeMedical
        res_actes = await db.execute(
            select(ActeMedical).where(
                ActeMedical.id.in_(payload.acte_ids),
                ActeMedical.clinic_id == current_user["clinic_id"]
            )
        )
        user.actes_pratiques = list(res_actes.scalars().all())

    try:
        after = _user_audit_snapshot(user)
        if before != after or payload.password is not None:
            action = "activation" if before["is_active"] != after["is_active"] else "modification"
            db.add(AuditLogTeam(
                clinic_id=current_user["clinic_id"],
                utilisateur_id=user.id,
                action=action,
                valeur_avant=before,
                valeur_apres=after,
                modifie_par_id=current_user["id"],
            ))
        await db.commit()
        result = await db.execute(
            select(Utilisateur)
            .options(selectinload(Utilisateur.actes_pratiques))
            .where(Utilisateur.id == user.id)
        )
        user = result.scalar_one()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning(
            "team_user_update_failed user_id=%s clinic_id=%s duration_ms=%.1f reason=integrity_error",
            user_id,
            current_user["clinic_id"],
            (time.perf_counter() - started_at) * 1000,
        )
        raise HTTPException(status_code=409, detail="Impossible de mettre à jour ce compte") from exc
    except Exception:
        await db.rollback()
        logger.warning(
            "team_user_update_failed user_id=%s clinic_id=%s duration_ms=%.1f reason=unexpected",
            user_id,
            current_user["clinic_id"],
            (time.perf_counter() - started_at) * 1000,
            exc_info=True,
        )
        raise

    logger.info(
        "team_user_update user_id=%s clinic_id=%s duration_ms=%.1f",
        user_id,
        current_user["clinic_id"],
        (time.perf_counter() - started_at) * 1000,
    )
    return _serialize_user(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    result = await db.execute(
        select(Utilisateur).where(
            Utilisateur.id == user_id,
            Utilisateur.clinic_id == current_user["clinic_id"],
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Compte introuvable")
    if user.id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    await _ensure_not_last_active_leader(db, user)
    await _ensure_not_last_active_leader_before_deactivation(db, user, True)

    before = _user_audit_snapshot(user)
    # Suppression logique : conserver les relations cliniques et anonymiser les
    # identifiants afin d'éviter une rupture de traçabilité ou de FK.
    user.email = f"anonymise-{user.id}@anonymized.invalid"
    user.nom = "Compte"
    user.prenom = "Anonymisé"
    user.telephone = None
    user.adresse = None
    user.specialite = None
    user.diplomes = None
    user.certifications = None
    user.documents_professionnels = None
    user.notes_internes = None
    user.hashed_password = get_password_hash(f"compte-anonymise-{user.id}")
    user.is_active = False
    db.add(AuditLogTeam(
        clinic_id=current_user["clinic_id"],
        utilisateur_id=user.id,
        action="suppression",
        valeur_avant=before,
        valeur_apres=_user_audit_snapshot(user),
        modifie_par_id=current_user["id"],
    ))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossible d'archiver ce membre : la transaction n'a pas pu être validée",
        ) from exc
    return None
