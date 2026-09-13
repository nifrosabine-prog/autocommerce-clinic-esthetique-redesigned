"""Bloc 3 — visibilité minimale des tâches internes déposées pour le staff
(notamment les suggestions de cascade après un ``NON`` patient). Sans cette
route, les tâches créées par ``services.remplacement_rdv.suggerer_cascade_apres_refus``
ou par le moteur de workflow (action ``create_task``) restent invisibles en
base — c'est précisément le défaut déjà constaté sur les réaffectations
d'absence, qu'on évite ici en construisant la vue en même temps que
l'écriture."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from models.security import StatutTacheInterneEnum, TacheInterneAssistant

router = APIRouter(prefix="/taches-internes", tags=["taches-internes"])
ROLES = (RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)


@router.get("")
async def list_taches(db: AsyncSession = Depends(get_db), current_user=Depends(require_role(*ROLES))):
    rows = (await db.execute(select(TacheInterneAssistant).where(
        TacheInterneAssistant.clinic_id == current_user["clinic_id"],
        TacheInterneAssistant.statut.in_([StatutTacheInterneEnum.A_FAIRE.value, StatutTacheInterneEnum.EN_COURS.value]),
    ).order_by(TacheInterneAssistant.created_at.desc()))).scalars().all()
    return [{"id": t.id, "titre": t.titre, "description": t.description, "priorite": t.priorite,
             "statut": t.statut, "patient_id": t.patient_id, "created_at": t.created_at} for t in rows]


@router.post("/{tache_id}/traiter")
async def marquer_traitee(tache_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(require_role(*ROLES))):
    tache = await db.scalar(select(TacheInterneAssistant).where(
        TacheInterneAssistant.id == tache_id, TacheInterneAssistant.clinic_id == current_user["clinic_id"],
    ))
    if not tache:
        raise HTTPException(status_code=404, detail="Tâche introuvable")
    tache.statut = StatutTacheInterneEnum.TERMINEE.value
    tache.updated_at = datetime.utcnow()
    await db.flush()
    return {"id": tache.id, "statut": tache.statut}
