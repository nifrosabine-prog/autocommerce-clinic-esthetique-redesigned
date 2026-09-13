"""Bloc F — exports patient privés."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from services.exports_patient import export_pdf, export_structured

router = APIRouter(prefix="/patients", tags=["patient-exports"])


def _meta(request: Request) -> dict:
    return {"ip_address": request.client.host if request.client else None}


def _raise(exc: Exception):
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{patient_id}/export-structured", response_model=dict)
async def export_patient_structured(patient_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        return await export_structured(db, patient_id, current_user, _meta(request))
    except Exception as exc:
        _raise(exc)


@router.get("/{patient_id}/export-pdf")
async def export_patient_pdf(patient_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        data = await export_pdf(db, patient_id, current_user, _meta(request))
        return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="patient_{patient_id}_clinical_export.pdf"'})
    except Exception as exc:
        _raise(exc)
