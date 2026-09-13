"""Routes privées de revue des demandes de réservation publiques."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import BookingRequest, RoleEnum, Utilisateur
from services.booking_requests import approve_booking_request, reject_booking_request

router = APIRouter(prefix="/booking-requests", tags=["booking-requests"])


class BookingRequestReject(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=500)


class BookingRequestAssign(BaseModel):
    praticien_id: int = Field(gt=0)


@router.get("")
async def list_booking_requests(
    statut: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    query = select(BookingRequest).where(BookingRequest.clinic_id == current_user["clinic_id"])
    if statut:
        query = query.where(BookingRequest.statut == statut)
    query = query.order_by(BookingRequest.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/{booking_request_id}/assign")
async def assign_booking_request(
    booking_request_id: int,
    payload: BookingRequestAssign,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    request = await db.scalar(select(BookingRequest).where(
        BookingRequest.id == booking_request_id,
        BookingRequest.clinic_id == current_user["clinic_id"],
    ))
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demande de réservation introuvable")
    if request.statut != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La demande a déjà été traitée")
    practitioner = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == payload.praticien_id,
        Utilisateur.clinic_id == current_user["clinic_id"],
        Utilisateur.is_active.is_(True),
        Utilisateur.role.in_([RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value]),
    ))
    if not practitioner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Praticien actif introuvable")
    request.praticien_id = practitioner.id
    await db.flush()
    return request


@router.post("/{booking_request_id}/approve")
async def approve_booking_request_route(
    booking_request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        return await approve_booking_request(
            booking_request_id,
            db,
            clinic_id=current_user["clinic_id"],
            reviewer_id=current_user["id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/{booking_request_id}/reject")
async def reject_booking_request_route(
    booking_request_id: int,
    payload: BookingRequestReject,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    try:
        return await reject_booking_request(
            booking_request_id,
            db,
            clinic_id=current_user["clinic_id"],
            reviewer_id=current_user["id"],
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
