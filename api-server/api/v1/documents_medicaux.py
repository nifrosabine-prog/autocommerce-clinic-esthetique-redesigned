"""Bloc D — documents médicaux patients, non publics."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from services.documents_medicaux import list_documents, read_document, soft_delete_document, upload_document

router = APIRouter(prefix="/patients", tags=["documents-medicaux"])


def _meta(request: Request) -> dict:
    return {"ip_address": request.client.host if request.client else None}


def _raise(exc: Exception):
    if isinstance(exc, PermissionError):
        raise HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{patient_id}/medical-documents", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_patient_medical_document(patient_id: int, request: Request, file: UploadFile = File(...), description: str | None = Form(None), consultation_id: int | None = Form(None), intervention_id: int | None = Form(None), db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        data = await file.read(25 * 1024 * 1024 + 1)
        if len(data) > 25 * 1024 * 1024:
            raise ValueError("Document trop volumineux")
        return await upload_document(db, patient_id, current_user, data, file.filename or "document", file.content_type or "application/octet-stream", description, consultation_id, intervention_id, _meta(request))
    except Exception as exc:
        _raise(exc)


@router.get("/{patient_id}/medical-documents", response_model=list[dict])
async def list_patient_medical_documents(patient_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        return await list_documents(db, patient_id, current_user, _meta(request))
    except Exception as exc:
        _raise(exc)


@router.get("/{patient_id}/medical-documents/{document_id}/download")
async def download_patient_medical_document(patient_id: int, document_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        item, data = await read_document(db, patient_id, document_id, current_user, _meta(request))
        return Response(content=data, media_type=item.mime_type, headers={"Content-Disposition": f'attachment; filename="{item.nom_original}"'})
    except Exception as exc:
        _raise(exc)


@router.delete("/{patient_id}/medical-documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient_medical_document(patient_id: int, document_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        await soft_delete_document(db, patient_id, document_id, current_user, _meta(request))
    except Exception as exc:
        _raise(exc)
