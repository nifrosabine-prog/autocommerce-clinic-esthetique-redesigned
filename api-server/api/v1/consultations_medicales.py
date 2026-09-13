"""Bloc A — consultations médicales structurées."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from services.consultations_medicales import create_consultation, get_consultation, list_consultations, update_consultation

router = APIRouter(prefix="/patients", tags=["consultations-medicales"])


class ConsultationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    episode_id: Optional[int] = None
    rdv_id: Optional[int] = None
    date_consultation: datetime
    type_consultation: str = Field(default="initiale", min_length=2, max_length=60)
    motif: Optional[str] = None
    demande_patient: Optional[str] = None
    objectif: Optional[str] = None
    histoire: Optional[str] = None
    evolution: Optional[str] = None
    traitements_precedents: Optional[str] = None
    contexte: Optional[str] = None
    observations_cliniques: Optional[str] = None
    mesures: Optional[str] = None
    diagnostic: Optional[str] = None
    indication: Optional[str] = None
    contre_indications: Optional[str] = None
    facteurs_risque: Optional[str] = None
    objectifs_therapeutiques: Optional[str] = None
    benefices_attendus: Optional[str] = None
    risques: Optional[str] = None
    alternatives: Optional[str] = None
    plan_therapeutique: Optional[str] = None
    recommandation: Optional[str] = None
    acte_propose: Optional[str] = None
    suivi: Optional[str] = None
    prochain_rdv_at: Optional[datetime] = None
    statut: str = Field(default="brouillon", pattern="^(brouillon|validee|archivee)$")


class ConsultationUpdate(ConsultationPayload):
    date_consultation: Optional[datetime] = None


def _meta(request: Request) -> dict:
    return {"ip_address": request.client.host if request.client else None, "user_agent": request.headers.get("user-agent")}


def _handle_error(exc: Exception) -> None:
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{patient_id}/consultations", response_model=dict, status_code=201)
async def create_patient_consultation(patient_id: int, data: ConsultationPayload, request: Request,
                                      db: AsyncSession = Depends(get_db),
                                      current_user=Depends(get_current_active_user)):
    try:
        item = await create_consultation(db, patient_id, current_user, data.model_dump(exclude_none=True), _meta(request))
        return {"id": item.id, "patient_id": item.patient_id, "episode_id": item.episode_id, "auteur_id": item.auteur_id,
                "date_consultation": item.date_consultation.isoformat(), "statut": item.statut}
    except Exception as exc:
        _handle_error(exc)


@router.get("/{patient_id}/consultations", response_model=list[dict])
async def list_patient_consultations(patient_id: int, request: Request,
                                     db: AsyncSession = Depends(get_db),
                                     current_user=Depends(get_current_active_user)):
    try:
        return await list_consultations(db, patient_id, current_user, _meta(request))
    except Exception as exc:
        _handle_error(exc)


@router.get("/{patient_id}/consultations/{consultation_id}", response_model=dict)
async def read_patient_consultation(patient_id: int, consultation_id: int, request: Request,
                                    db: AsyncSession = Depends(get_db),
                                    current_user=Depends(get_current_active_user)):
    try:
        return await get_consultation(db, consultation_id, patient_id, current_user, _meta(request))
    except Exception as exc:
        _handle_error(exc)


@router.patch("/{patient_id}/consultations/{consultation_id}", response_model=dict)
async def update_patient_consultation(patient_id: int, consultation_id: int, data: ConsultationUpdate,
                                      request: Request, db: AsyncSession = Depends(get_db),
                                      current_user=Depends(get_current_active_user)):
    try:
        return await update_consultation(db, consultation_id, patient_id, current_user,
                                         data.model_dump(exclude_unset=True), _meta(request))
    except Exception as exc:
        _handle_error(exc)
