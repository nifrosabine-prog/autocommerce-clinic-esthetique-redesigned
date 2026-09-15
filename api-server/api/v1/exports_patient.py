"""Bloc F — exports patient privés.

NOTE CORRECTIF (collision de route) :
Ce router partage le préfixe "/patients" avec dossiers_medicaux.py, qui est
enregistré AVANT ce router dans api/v1/__init__.py et expose déjà
GET /{patient_id}/export-pdf (export complet enrichi v2, déjà utilisé par le
frontend via client/src/lib/api.ts). FastAPI fait un matching "premier
enregistré gagne" : les deux routes identiques faisaient que cet endpoint
n'était jamais atteint, quel que soit l'appelant. Déplacé vers
/export-pdf-global pour ne plus collisionner (non branché sur le frontend,
volontairement, à ce stade).
"""
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


@router.get("/{patient_id}/export-pdf-global")
async def export_patient_pdf(patient_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    """Export PDF du Dossier Patient Global (blocs A-J).

    Anciennement monté sur /{patient_id}/export-pdf, en collision silencieuse
    avec dossiers_medicaux.py (voir note en tête de fichier).
    """
    try:
        data = await export_pdf(db, patient_id, current_user, _meta(request))
        return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="patient_{patient_id}_dossier_global.pdf"'})
    except Exception as exc:
        _raise(exc)
