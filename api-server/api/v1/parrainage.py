from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from api.deps import get_db, require_role
from models.database import RoleEnum
from services.parrainage import (
    ParrainageService,
    PatientParrainageNotFound,
    ParrainageInvalid,
)

router = APIRouter(prefix="/parrainage", tags=["parrainage"])


class ParrainageUse(BaseModel):
    code: str = Field(min_length=3, max_length=32)
    filleul_id: int = Field(gt=0)


_ALLOWED_ROLES = [RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE]


@router.get("/code/{patient_id}")
async def get_code_parrain(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(_ALLOWED_ROLES)),
):
    clinic_id = current_user.get("clinic_id")
    if not clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contexte clinique absent",
        )
    try:
        code = await ParrainageService.get_ou_creer_code(
            db, patient_id, clinic_id=clinic_id
        )
    except PatientParrainageNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return {"code": code}


@router.post("/utiliser")
async def utiliser_code(
    data: ParrainageUse,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(_ALLOWED_ROLES)),
):
    clinic_id = current_user.get("clinic_id")
    if not clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contexte clinique absent",
        )
    try:
        success = await ParrainageService.utiliser_code(
            db, data.code, data.filleul_id, clinic_id=clinic_id
        )
    except PatientParrainageNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ParrainageInvalid as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code invalide ou patient hors clinique",
        )
    return {"status": "success"}


@router.get("/filleuls/{parrain_id}")
async def get_filleuls(
    parrain_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(_ALLOWED_ROLES)),
):
    clinic_id = current_user.get("clinic_id")
    if not clinic_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Contexte clinique absent",
        )
    try:
        filleuls = await ParrainageService.get_filleuls(
            db, parrain_id, clinic_id=clinic_id
        )
    except PatientParrainageNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return [
        {
            "id": p.id,
            "filleul_id": p.filleul_patient_id,
            "date": p.date_parrainage,
            "recompense_attribuee": p.recompense_attribuee,
        }
        for p in filleuls
    ]
