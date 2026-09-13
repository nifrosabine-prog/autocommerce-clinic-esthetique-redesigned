from typing import List, Optional
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum, LaboratoirePartenaire, DelegueMedical, VisiteDelegue

router = APIRouter(prefix="/delegues", tags=["delegues"])

class LaboCreate(BaseModel):
    nom: str
    contact_nom: Optional[str] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    adresse: Optional[str] = None

class DelegueCreate(BaseModel):
    labo_id: int
    nom: str
    prenom: str
    telephone: Optional[str] = None
    email: Optional[str] = None

class VisiteCreate(BaseModel):
    delegue_id: int
    medecin_id: Optional[int] = None
    date_visite: datetime
    objet: str
    compte_rendu: Optional[str] = None
    echantillons_recus: Optional[dict] = None

@router.get("/delegues", response_model=List[dict])
async def list_delegues(db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN))):
    result = await db.execute(
        select(DelegueMedical).where(DelegueMedical.clinic_id == current_user["clinic_id"]).order_by(DelegueMedical.nom, DelegueMedical.prenom)
    )
    return [{"id": d.id, "nom": d.nom, "prenom": d.prenom, "nom_complet": f"{d.prenom} {d.nom}", "labo_id": d.labo_id} for d in result.scalars().all()]

@router.post("/delegues", status_code=status.HTTP_201_CREATED)
async def create_delegue(payload: DelegueCreate, db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE))):
    labo = await db.scalar(select(LaboratoirePartenaire).where(LaboratoirePartenaire.id == payload.labo_id, LaboratoirePartenaire.clinic_id == current_user["clinic_id"]))
    if not labo:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Laboratoire non trouvé")
    delegue = DelegueMedical(**payload.model_dump(), clinic_id=current_user["clinic_id"])
    db.add(delegue)
    await db.commit()
    await db.refresh(delegue)
    return {"id": delegue.id, "nom": delegue.nom, "prenom": delegue.prenom, "nom_complet": f"{delegue.prenom} {delegue.nom}", "labo_id": delegue.labo_id}

@router.get("/labos", response_model=List[dict])
async def list_labos(db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN))):
    result = await db.execute(select(LaboratoirePartenaire).where(LaboratoirePartenaire.clinic_id == current_user["clinic_id"]))
    labos = result.scalars().all()
    return [{"id": labo.id, "nom": labo.nom, "contact": labo.contact_nom} for labo in labos]

@router.post("/labos", status_code=status.HTTP_201_CREATED)
async def create_labo(payload: LaboCreate, db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE))):
    labo = LaboratoirePartenaire(**payload.model_dump(), clinic_id=current_user["clinic_id"])
    db.add(labo)
    await db.commit()
    await db.refresh(labo)
    return labo

@router.get("/visites", response_model=List[dict])
async def list_visites(db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN))):
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(VisiteDelegue)
        .options(joinedload(VisiteDelegue.delegue))
        .where(VisiteDelegue.clinic_id == current_user["clinic_id"])
        .order_by(VisiteDelegue.date_visite.desc())
    )
    visites = result.scalars().all()
    return [{
        "id": v.id,
        "date": v.date_visite,
        "delegue": f"{v.delegue.prenom} {v.delegue.nom}",
        "objet": v.objet,
        "echantillons": v.echantillons_recus
    } for v in visites]

@router.post("/visites", status_code=status.HTTP_201_CREATED)

async def create_visite(payload: VisiteCreate, db: AsyncSession = Depends(get_db), current_user=Depends(require_role(RoleEnum.ADMIN, RoleEnum.DIRECTRICE, RoleEnum.MEDECIN))):
    values = payload.model_dump()
    visit_dt = values.get("date_visite")
    if visit_dt is not None and visit_dt.tzinfo is not None:
        # La colonne PostgreSQL est TIMESTAMP WITHOUT TIME ZONE : on stocke une
        # valeur UTC naïve pour éviter le mélange aware/naive envoyé par le navigateur.
        values["date_visite"] = visit_dt.astimezone(timezone.utc).replace(tzinfo=None)
    visite = VisiteDelegue(**values, clinic_id=current_user["clinic_id"])
    db.add(visite)
    await db.commit()
    await db.refresh(visite)
    return visite
