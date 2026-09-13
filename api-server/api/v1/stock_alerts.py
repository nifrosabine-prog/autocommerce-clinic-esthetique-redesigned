"""API des rappels de seuil stock persistants."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services.stock_alerts import acknowledge_stock_alert, list_active_stock_alerts
from services.tenant_scope import resolve_clinic_id

router = APIRouter(prefix="/stock-alertes", tags=["stock-alertes"])
GESTIONNAIRES = (RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE)


@router.get("", response_model=list[dict])
async def get_stock_alerts(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*GESTIONNAIRES)),
):
    clinic_id = resolve_clinic_id(current_user.get("clinic_id"))
    return await list_active_stock_alerts(db, clinic_id)


@router.post("/{alert_id}/acquitter", response_model=dict)
async def acknowledge_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*GESTIONNAIRES)),
):
    clinic_id = resolve_clinic_id(current_user.get("clinic_id"))
    acknowledged = await acknowledge_stock_alert(db, alert_id, clinic_id, int(current_user["id"]))
    if not acknowledged:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rappel introuvable ou déjà traité")
    await db.commit()
    return {"status": "success", "alert_id": alert_id}
