"""Gestion sécurisée des comptes de l'équipe clinique."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_db
from middleware.auth import get_password_hash
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, Utilisateur


router = APIRouter(prefix="/users", tags=["users"])

MANAGE_ROLES = (RoleEnum.DIRECTRICE, RoleEnum.ADMIN)
CLINIC_ASSIGNABLE_ROLES = {
    RoleEnum.DIRECTRICE,
    RoleEnum.ADMIN,
    RoleEnum.MEDECIN,
    RoleEnum.ESTHETICIENNE,
    RoleEnum.ASSISTANTE,
    RoleEnum.COMMERCIAL,
}
PUBLIC_PRACTITIONER_ROLES = {RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE}


def _validate_clinic_assignable_role(role: Optional[RoleEnum]) -> None:
    """A clinic administrator must never mint a platform-global role."""
    if role is None:
        return
    if role not in CLINIC_ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le rôle demandé ne peut pas être attribué depuis une clinique",
        )


def _validate_public_practitioner(*, role: RoleEnum | str, is_active: bool, is_public: bool) -> None:
    normalized_role = role.value if isinstance(role, RoleEnum) else str(role)
    if is_public and normalized_role not in {item.value for item in PUBLIC_PRACTITIONER_ROLES}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Seuls les médecins et esthéticiennes peuvent être publiés à la réservation.")
    if is_public and not is_active:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Un praticien doit être actif avant d’être publié à la réservation.")


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
    is_public: bool = False
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


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    _validate_clinic_assignable_role(payload.role)
    _validate_public_practitioner(role=payload.role, is_active=True, is_public=payload.is_public)
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
        is_active=True,
        is_public=payload.is_public,
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
    next_role = payload.role if payload.role is not None else user.role
    next_active = payload.is_active if payload.is_active is not None else user.is_active
    next_public = payload.is_public if payload.is_public is not None else user.is_public
    _validate_public_practitioner(role=next_role, is_active=next_active, is_public=next_public)
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
        await db.commit()
        result = await db.execute(
            select(Utilisateur)
            .options(selectinload(Utilisateur.actes_pratiques))
            .where(Utilisateur.id == user.id)
        )
        user = result.scalar_one()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Impossible de mettre à jour ce compte") from exc

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
    
    await db.delete(user)
    await db.commit()
    return None
