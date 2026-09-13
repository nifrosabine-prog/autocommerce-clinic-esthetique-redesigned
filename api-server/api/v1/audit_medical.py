"""Bloc G — audit médical privé."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from services.audit_medical_query import query_medical_audit

router = APIRouter(prefix="/audit", tags=["medical-audit"])


@router.get("/medical", response_model=list[dict])
async def medical_audit(patient_id: Optional[int] = Query(None, ge=1), action: Optional[str] = Query(None, max_length=100), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db), current_user=Depends(get_current_active_user)):
    try:
        return await query_medical_audit(db, current_user, patient_id, action, limit, offset)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
