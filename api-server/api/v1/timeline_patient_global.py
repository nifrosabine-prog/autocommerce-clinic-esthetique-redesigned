"""Bloc E — chronologie patient globale."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from services.timeline_patient_global import get_global_timeline

router = APIRouter(prefix="/patients", tags=["patient-timeline"])


@router.get("/{patient_id}/global-timeline", response_model=list[dict])
async def patient_global_timeline(patient_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        return await get_global_timeline(db, patient_id, current_user, {"ip_address": request.client.host if request.client else None})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
