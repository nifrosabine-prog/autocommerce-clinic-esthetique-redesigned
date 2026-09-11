from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from api.deps import get_db, require_role
from models.database import RoleEnum
from services.parrainage import ParrainageService

router = APIRouter(prefix="/parrainage", tags=["parrainage"])


class ParrainageUse(BaseModel):
    code: str = Field(min_length=3, max_length=32)
    filleul_id: int


_ALLOWED_ROLES = [RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE]


@router.get("/code/{patient_id}")
async def get_code_parrain(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(_ALLOWED_ROLES)),
):
    code = await ParrainageService.get_ou_creer_code(
        db, patient_id, clinic_id=current_user["clinic_id"]
    )
    return {"code": code}


@router.post("/utiliser")
async def utiliser_code(
    data: ParrainageUse,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(_ALLOWED_ROLES)),
):
    success = await ParrainageService.utiliser_code(
        db, data.code, data.filleul_id, clinic_id=current_user["clinic_id"]
    )
    if not success:
        raise HTTPException(status_code=400, detail="Code invalide, déjà utilisé ou patient hors clinique")
    return {"status": "success"}


@router.get("/filleuls/{parrain_id}")
async def get_filleuls(
    parrain_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(_ALLOWED_ROLES)),
):
    filleuls = await ParrainageService.get_filleuls(
        db, parrain_id, clinic_id=current_user["clinic_id"]
    )
    return [
        {
            "id": p.id,
            "filleul_id": p.filleul_patient_id,
            "date": p.date_parrainage,
            "recompense_attribuee": p.recompense_attribuee,
        }
        for p in filleuls
    ]
