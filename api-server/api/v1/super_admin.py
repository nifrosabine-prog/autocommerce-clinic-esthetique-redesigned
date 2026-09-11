from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.super_admin import (
    get_clinic_stats,
    get_dashboard,
    get_performance_metrics,
    get_system_health,
    list_all_users,
    list_clinics,
    list_subscriptions,
    update_subscription,
)

router = APIRouter(prefix="/super-admin", tags=["super-admin"])


class SubscriptionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clinic_name: str | None = Field(default=None, min_length=2, max_length=200)
    plan: str | None = Field(default=None, min_length=2, max_length=50)
    status: str | None = Field(default=None, pattern="^(active|trial|past_due|suspended|cancelled)$")
    expires_at: datetime | None = None
    monthly_amount: Decimal | None = Field(default=None, ge=0)
    max_users: int | None = Field(default=None, ge=1, le=100000)
    notes: str | None = Field(default=None, max_length=2000)
    last_payment_at: datetime | None = None


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(RoleEnum.SUPER_ADMIN)),
):
    return await get_dashboard(db)


@router.get("/clinics")
async def clinics(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(RoleEnum.SUPER_ADMIN)),
):
    return await list_clinics(db)


@router.get("/clinics/{clinic_id}")
async def clinic_detail(
    clinic_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(RoleEnum.SUPER_ADMIN)),
):
    return await get_clinic_stats(db, clinic_id)


@router.get("/users")
async def users(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(RoleEnum.SUPER_ADMIN)),
):
    return await list_all_users(db)


@router.get("/health")
async def health(
    current_user: dict = Depends(require_role(RoleEnum.SUPER_ADMIN)),
):
    return await get_system_health()


@router.get("/performance")
async def performance(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(RoleEnum.SUPER_ADMIN)),
):
    return await get_performance_metrics(db)


@router.get("/subscriptions")
async def subscriptions(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(RoleEnum.SUPER_ADMIN)),
):
    return await list_subscriptions(db)


@router.patch("/subscriptions/{subscription_id}")
async def patch_subscription(
    subscription_id: int,
    payload: SubscriptionPatch,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role(RoleEnum.SUPER_ADMIN)),
):
    changes = payload.model_dump(exclude_unset=True)
    result = await update_subscription(db, subscription_id, changes)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Abonnement introuvable")
    return result
