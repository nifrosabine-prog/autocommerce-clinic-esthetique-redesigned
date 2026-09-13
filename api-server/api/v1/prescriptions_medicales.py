"""Bloc C — prescriptions médicales."""
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from services.prescriptions_medicales import create_prescription, list_prescriptions

router = APIRouter(prefix="/patients", tags=["prescriptions-medicales"])


class PrescriptionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    episode_id: Optional[int] = None
    consultation_id: Optional[int] = None
    intervention_id: Optional[int] = None
    acte_id: Optional[int] = None
    date_prescription: Optional[datetime] = None
    details: dict[str, Any]
    statut: str = Field(default="ACTIVE", pattern="^(ACTIVE|CANCELLED|COMPLETED)$")


def _meta(request: Request) -> dict:
    return {"ip_address": request.client.host if request.client else None}


def _raise(exc: Exception):
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{patient_id}/prescriptions", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_patient_prescription(patient_id: int, data: PrescriptionPayload, request: Request,
                                      db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        return await create_prescription(db, patient_id, current_user, data.model_dump(), _meta(request))
    except Exception as exc:
        _raise(exc)


@router.get("/{patient_id}/prescriptions", response_model=list[dict])
async def list_patient_prescriptions(patient_id: int, request: Request,
                                     db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        return await list_prescriptions(db, patient_id, current_user, _meta(request))
    except Exception as exc:
        _raise(exc)
