"""Consultation et validation humaine des créneaux proposés après annulation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, SuggestionRemplacementRdv
from services.remplacement_rdv import valider_suggestion

router = APIRouter(prefix="/agenda", tags=["remplacements-rdv"])
ROLES = (RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)


@router.get("/suggestions-remplacement")
async def list_replacement_suggestions(db: AsyncSession = Depends(get_db), current_user=Depends(require_role(*ROLES))):
    rows = (await db.execute(select(SuggestionRemplacementRdv).where(
        SuggestionRemplacementRdv.clinic_id == current_user["clinic_id"],
        SuggestionRemplacementRdv.statut == "a_valider",
    ).order_by(SuggestionRemplacementRdv.date_heure_debut))).scalars().all()
    return [{"id": row.id, "rdv_annule_id": row.rdv_annule_id, "praticien_id": row.praticien_id,
             "date_heure_debut": row.date_heure_debut, "date_heure_fin": row.date_heure_fin,
             "statut": row.statut} for row in rows]


@router.post("/suggestions-remplacement/{suggestion_id}/valider")
async def validate_replacement_suggestion(suggestion_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(require_role(*ROLES))):
    try:
        replacement = await valider_suggestion(db, suggestion_id, clinic_id=current_user["clinic_id"], validated_by=int(current_user["id"]))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"message": "Créneau validé et nouveau rendez-vous créé", "rdv_id": replacement.id,
            "remplace_rdv_id": replacement.remplace_rdv_id}
