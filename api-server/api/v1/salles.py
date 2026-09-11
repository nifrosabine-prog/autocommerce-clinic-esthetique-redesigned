"""Gestion des salles de la clinique."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, Salle


router = APIRouter(prefix="/salles", tags=["salles"])

MANAGE_ROLES = (RoleEnum.DIRECTRICE, RoleEnum.ADMIN)


class SalleCreate(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)


class SalleOut(BaseModel):
    id: int
    nom: str
    type: str
    description: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


def _serialize_salle(salle: Salle) -> dict:
    return {
        "id": salle.id,
        "nom": salle.nom,
        "type": salle.type,
        "description": salle.description,
        "is_active": salle.is_active,
    }


@router.get("", response_model=list[SalleOut])
async def list_salles(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    result = await db.execute(
        select(Salle)
        .where(Salle.clinic_id == current_user["clinic_id"])
        .order_by(Salle.nom)
    )
    return [_serialize_salle(salle) for salle in result.scalars().all()]


@router.post("", response_model=SalleOut, status_code=status.HTTP_201_CREATED)
async def create_salle(
    payload: SalleCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    salle = Salle(
        clinic_id=current_user["clinic_id"],
        nom=payload.nom.strip(),
        type=payload.type.strip(),
        description=payload.description,
        is_active=True,
    )
    db.add(salle)
    await db.commit()
    await db.refresh(salle)
    return _serialize_salle(salle)


@router.patch("/{salle_id}", response_model=SalleOut)
async def update_salle(
    salle_id: int,
    payload: SalleCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    result = await db.execute(
        select(Salle).where(
            Salle.id == salle_id,
            Salle.clinic_id == current_user["clinic_id"],
        )
    )
    salle = result.scalar_one_or_none()
    if not salle:
        raise HTTPException(status_code=404, detail="Salle introuvable")

    salle.nom = payload.nom.strip()
    salle.type = payload.type.strip()
    salle.description = payload.description
    
    await db.commit()
    await db.refresh(salle)
    return _serialize_salle(salle)


@router.delete("/{salle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_salle(
    salle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*MANAGE_ROLES)),
):
    result = await db.execute(
        select(Salle).where(
            Salle.id == salle_id,
            Salle.clinic_id == current_user["clinic_id"],
        )
    )
    salle = result.scalar_one_or_none()
    if not salle:
        raise HTTPException(status_code=404, detail="Salle introuvable")
    
    await db.delete(salle)
    await db.commit()
    return None
