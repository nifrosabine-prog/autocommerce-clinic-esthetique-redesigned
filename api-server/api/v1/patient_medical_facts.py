"""Bloc B — données médicales structurées du patient."""
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from services.patient_medical_facts import create_fact, list_facts, soft_delete_fact

router = APIRouter(prefix="/patients", tags=["patient-medical-facts"])


class MedicalFactPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    episode_id: Optional[int] = None
    type_fait: str = Field(min_length=3, max_length=40)
    donnees: dict[str, Any]
    source: str = Field(default="MANUAL", pattern="^(MANUAL|MIGRATED)$")
    verification_status: str = Field(default="VERIFIED", pattern="^(VERIFIED|PENDING_VERIFICATION|HISTORICAL_UNSTRUCTURED)$")


def _meta(request: Request) -> dict:
    return {"ip_address": request.client.host if request.client else None, "user_agent": request.headers.get("user-agent")}


def _error(exc: Exception):
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{patient_id}/medical-facts", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_patient_medical_fact(patient_id: int, data: MedicalFactPayload, request: Request,
                                      db: AsyncSession = Depends(get_db),
                                      current_user=Depends(get_current_active_user)):
    try:
        return await create_fact(db, patient_id, current_user, data.model_dump(), _meta(request))
    except Exception as exc:
        _error(exc)


@router.get("/{patient_id}/medical-facts", response_model=list[dict])
async def list_patient_medical_facts(patient_id: int, request: Request,
                                     db: AsyncSession = Depends(get_db),
                                     current_user=Depends(get_current_active_user)):
    try:
        return await list_facts(db, patient_id, current_user, _meta(request))
    except Exception as exc:
        _error(exc)


@router.delete("/{patient_id}/medical-facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient_medical_fact(patient_id: int, fact_id: int, request: Request,
                                      db: AsyncSession = Depends(get_db),
                                      current_user=Depends(get_current_active_user)):
    try:
        await soft_delete_fact(db, patient_id, fact_id, current_user, _meta(request))
    except Exception as exc:
        _error(exc)
