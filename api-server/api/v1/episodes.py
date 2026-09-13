"""Épisodes et propositions professionnelles — fondation du bloc 5."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from models.database import ActeMedical, Patient, Utilisateur
from models.episode_core import (
    EpisodePatient, Intervention, InterventionActe, StatutIntervention,
)
from services.access_control import clinic_id_for

router = APIRouter(prefix="/episodes", tags=["episodes"])

ROLE_TYPES = {"medecin": "medical", "estheticienne": "esthetique", "prestataire": "massage"}


def role(user: dict) -> str:
    return str(user.get("role", "")).replace("RoleEnum.", "").lower()


async def episode_scope(db: AsyncSession, episode_id: int, user: dict) -> EpisodePatient:
    episode = await db.scalar(select(EpisodePatient).where(
        EpisodePatient.id == episode_id, EpisodePatient.clinic_id == clinic_id_for(user),
    ))
    if not episode:
        raise HTTPException(status_code=404, detail="Épisode introuvable")
    return episode


async def intervention_scope(db: AsyncSession, episode: EpisodePatient, intervention_id: int) -> Intervention:
    intervention = await db.scalar(select(Intervention).where(
        Intervention.id == intervention_id,
        Intervention.episode_id == episode.id,
        Intervention.clinic_id == episode.clinic_id,
    ))
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention introuvable")
    return intervention


class InterventionCreate(BaseModel):
    professionnel_id: Optional[int] = None
    rdv_id: Optional[int] = None
    type_intervention: Optional[str] = None
    date_debut_prevue: Optional[datetime] = None


class ActeProposalCreate(BaseModel):
    acte_id: int
    prix_convenu: Decimal = Field(default=Decimal("0"), ge=0)


@router.get("/{episode_id}")
async def get_episode(episode_id: int, current_user: dict = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    episode = await episode_scope(db, episode_id, current_user)
    rows = (await db.execute(select(Intervention).where(
        Intervention.episode_id == episode.id, Intervention.clinic_id == episode.clinic_id,
    ).order_by(Intervention.id))).scalars().all()
    payload = []
    for intervention in rows:
        acts = (await db.execute(select(InterventionActe, ActeMedical).join(
            ActeMedical, ActeMedical.id == InterventionActe.acte_id,
        ).where(InterventionActe.intervention_id == intervention.id))).all()
        payload.append({
            "id": intervention.id, "professionnel_id": intervention.professionnel_id,
            "rdv_id": intervention.rdv_id, "type_intervention": intervention.type_intervention,
            "statut": intervention.statut,
            "actes": [{"id": line.id, "acte_id": line.acte_id, "nom": acte.nom,
                       "statut": line.statut, "prix_convenu": str(line.prix_convenu),
                       "accepte_medical": line.accepte_medical,
                       "accepte_financier": line.accepte_financier, "realise": line.realise}
                      for line, acte in acts],
        })
    return {"id": episode.id, "patient_id": episode.patient_id, "statut": episode.statut, "interventions": payload}


@router.post("/{episode_id}/interventions", status_code=201)
async def create_intervention(episode_id: int, data: InterventionCreate, current_user: dict = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    episode = await episode_scope(db, episode_id, current_user)
    current_role = role(current_user)
    if current_role not in ROLE_TYPES and current_role not in {"directrice", "admin"}:
        raise HTTPException(status_code=403, detail="Ce rôle ne peut pas créer une intervention")
    professional_id = data.professionnel_id or int(current_user["id"])
    professional = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == professional_id, Utilisateur.clinic_id == episode.clinic_id, Utilisateur.is_active,
    ))
    if not professional:
        raise HTTPException(status_code=404, detail="Professionnel introuvable dans cette clinique")
    if current_role in ROLE_TYPES and professional_id != int(current_user["id"]):
        raise HTTPException(status_code=403, detail="Un professionnel ne peut créer que sa propre intervention")
    intervention_type = data.type_intervention or ROLE_TYPES.get(role({"role": professional.role}), "autre")
    intervention = Intervention(clinic_id=episode.clinic_id, episode_id=episode.id,
                               professionnel_id=professional_id, rdv_id=data.rdv_id,
                               type_intervention=intervention_type,
                               date_debut_prevue=data.date_debut_prevue)
    db.add(intervention)
    await db.commit()
    return {"id": intervention.id, "episode_id": episode.id, "professionnel_id": professional_id, "statut": intervention.statut}


@router.post("/{episode_id}/interventions/{intervention_id}/actes", status_code=201)
async def propose_acte(episode_id: int, intervention_id: int, data: ActeProposalCreate, current_user: dict = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    episode = await episode_scope(db, episode_id, current_user)
    if role(current_user) not in set(ROLE_TYPES) | {"directrice"}:
        raise HTTPException(status_code=403, detail="La proposition d'actes est réservée aux professionnels de soin")
    intervention = await intervention_scope(db, episode, intervention_id)
    if role(current_user) in ROLE_TYPES and intervention.professionnel_id != int(current_user["id"]):
        raise HTTPException(status_code=403, detail="Cette intervention est affectée à un autre professionnel")
    acte = await db.scalar(select(ActeMedical).where(
        ActeMedical.id == data.acte_id, ActeMedical.clinic_id == episode.clinic_id, ActeMedical.is_active,
    ))
    if not acte:
        raise HTTPException(status_code=404, detail="Acte non autorisé dans cette clinique")
    line = InterventionActe(clinic_id=episode.clinic_id, intervention_id=intervention.id,
                            acte_id=acte.id,
                            prix_convenu=data.prix_convenu if role(current_user) == "directrice" else acte.prix_base,
                            propose_par_id=int(current_user["id"]))
    db.add(line)
    await db.commit()
    return {"id": line.id, "intervention_id": intervention.id, "acte_id": acte.id, "statut": line.statut, "prix_convenu": str(line.prix_convenu)}


@router.post("/{episode_id}/interventions/{intervention_id}/actes/{acte_line_id}/valider-medical")
async def validate_medical_act(episode_id: int, intervention_id: int, acte_line_id: int, current_user: dict = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    if role(current_user) not in {"medecin", "directrice"}:
        raise HTTPException(status_code=403, detail="Validation médicale réservée au médecin ou à la direction")
    episode = await episode_scope(db, episode_id, current_user)
    await intervention_scope(db, episode, intervention_id)
    line = await db.scalar(select(InterventionActe).where(
        InterventionActe.id == acte_line_id, InterventionActe.intervention_id == intervention_id,
        InterventionActe.clinic_id == episode.clinic_id,
    ))
    if not line:
        raise HTTPException(status_code=404, detail="Acte proposé introuvable")
    if line.accepte_medical:
        return {"id": line.id, "statut": line.statut, "accepte_medical": True}
    line.accepte_medical = True
    line.accepte_medical_par_id = int(current_user["id"])
    line.accepte_medical_le = datetime.utcnow()
    line.statut = "accepte_medical"
    await db.commit()
    return {"id": line.id, "statut": line.statut, "accepte_medical": True}


@router.post("/{episode_id}/interventions/{intervention_id}/actes/{acte_line_id}/valider-financier")
async def validate_financial_act(episode_id: int, intervention_id: int, acte_line_id: int, current_user: dict = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    if role(current_user) not in {"assistante", "directrice", "admin"}:
        raise HTTPException(status_code=403, detail="Validation financière réservée à l'accueil ou à la direction")
    episode = await episode_scope(db, episode_id, current_user)
    await intervention_scope(db, episode, intervention_id)
    line = await db.scalar(select(InterventionActe).where(
        InterventionActe.id == acte_line_id, InterventionActe.intervention_id == intervention_id,
        InterventionActe.clinic_id == episode.clinic_id,
    ))
    if not line:
        raise HTTPException(status_code=404, detail="Acte proposé introuvable")
    if not line.accepte_medical:
        raise HTTPException(status_code=409, detail="La validation médicale est requise avant la validation financière")
    if line.accepte_financier:
        return {"id": line.id, "statut": line.statut, "accepte_financier": True}
    line.accepte_financier = True
    line.accepte_financier_par_id = int(current_user["id"])
    line.accepte_financier_le = datetime.utcnow()
    if line.accepte_medical:
        line.statut = "accepte"
    await db.commit()
    return {"id": line.id, "statut": line.statut, "accepte_financier": True}


async def _owned_intervention(db: AsyncSession, episode: EpisodePatient, intervention_id: int, current_user: dict) -> Intervention:
    intervention = await intervention_scope(db, episode, intervention_id)
    current_role = role(current_user)
    if current_role in ROLE_TYPES and intervention.professionnel_id != int(current_user["id"]):
        raise HTTPException(status_code=403, detail="Cette intervention est affectée à un autre professionnel")
    if current_role not in set(ROLE_TYPES) | {"directrice"}:
        raise HTTPException(status_code=403, detail="Rôle non autorisé pour cette transition")
    return intervention


@router.post("/{episode_id}/interventions/{intervention_id}/demarrer")
async def start_intervention(
    episode_id: int,
    intervention_id: int,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    episode = await episode_scope(db, episode_id, current_user)
    intervention = await _owned_intervention(db, episode, intervention_id, current_user)
    if intervention.statut == StatutIntervention.EN_COURS.value:
        return {"id": intervention.id, "statut": intervention.statut, "demarree_le": intervention.demarree_le}
    if intervention.statut != StatutIntervention.PLANIFIEE.value:
        raise HTTPException(status_code=409, detail=f"Démarrage impossible depuis le statut {intervention.statut}")
    lines = (await db.execute(select(InterventionActe).where(
        InterventionActe.intervention_id == intervention.id,
    ))).scalars().all()
    if not lines:
        raise HTTPException(status_code=409, detail="Impossible de démarrer une intervention sans acte")
    if any(not line.accepte_medical or not line.accepte_financier for line in lines):
        raise HTTPException(status_code=409, detail="Tous les actes doivent être validés médicalement et financièrement")
    intervention.statut = StatutIntervention.EN_COURS.value
    intervention.demarree_le = datetime.utcnow()
    await db.commit()
    return {"id": intervention.id, "statut": intervention.statut, "demarree_le": intervention.demarree_le}


@router.post("/{episode_id}/interventions/{intervention_id}/actes/{acte_line_id}/realiser")
async def realize_act(
    episode_id: int,
    intervention_id: int,
    acte_line_id: int,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    episode = await episode_scope(db, episode_id, current_user)
    intervention = await _owned_intervention(db, episode, intervention_id, current_user)
    if intervention.statut != StatutIntervention.EN_COURS.value:
        raise HTTPException(status_code=409, detail="L’intervention doit être en cours pour réaliser un acte")
    line = await db.scalar(select(InterventionActe).where(
        InterventionActe.id == acte_line_id,
        InterventionActe.intervention_id == intervention.id,
        InterventionActe.clinic_id == episode.clinic_id,
    ))
    if not line:
        raise HTTPException(status_code=404, detail="Acte introuvable dans cette intervention")
    if line.realise:
        return {"id": line.id, "statut": line.statut, "realise": True}
    if not line.accepte_medical or not line.accepte_financier:
        raise HTTPException(status_code=409, detail="L’acte doit être validé médicalement et financièrement")
    line.realise = True
    line.realise_par_id = int(current_user["id"])
    line.realise_le = datetime.utcnow()
    line.statut = "realise"
    await db.commit()
    return {"id": line.id, "statut": line.statut, "realise": True}


@router.post("/{episode_id}/interventions/{intervention_id}/a-valider")
async def mark_intervention_for_validation(
    episode_id: int,
    intervention_id: int,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    episode = await episode_scope(db, episode_id, current_user)
    intervention = await _owned_intervention(db, episode, intervention_id, current_user)
    if intervention.statut == StatutIntervention.A_VALIDER.value:
        return {"id": intervention.id, "statut": intervention.statut}
    if intervention.statut != StatutIntervention.EN_COURS.value:
        raise HTTPException(status_code=409, detail=f"Passage en validation impossible depuis le statut {intervention.statut}")
    lines = (await db.execute(select(InterventionActe).where(InterventionActe.intervention_id == intervention.id))).scalars().all()
    if not lines or any(not line.realise for line in lines):
        raise HTTPException(status_code=409, detail="Tous les actes doivent être réalisés avant validation")
    intervention.statut = StatutIntervention.A_VALIDER.value
    intervention.terminee_le = datetime.utcnow()
    await db.commit()
    return {"id": intervention.id, "statut": intervention.statut}


@router.post("/{episode_id}/interventions/{intervention_id}/cloturer")
async def close_intervention(
    episode_id: int,
    intervention_id: int,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    episode = await episode_scope(db, episode_id, current_user)
    intervention = await _owned_intervention(db, episode, intervention_id, current_user)
    if intervention.statut == StatutIntervention.TERMINEE.value:
        return {"id": intervention.id, "statut": intervention.statut}
    if intervention.statut != StatutIntervention.A_VALIDER.value:
        raise HTTPException(status_code=409, detail="Une intervention doit être à valider avant clôture")
    lines = (await db.execute(select(InterventionActe).where(InterventionActe.intervention_id == intervention.id))).scalars().all()
    if not lines or any(not line.realise for line in lines):
        raise HTTPException(status_code=409, detail="La clôture exige tous les actes réalisés")
    intervention.statut = StatutIntervention.TERMINEE.value
    intervention.terminee_le = intervention.terminee_le or datetime.utcnow()
    await db.commit()
    return {"id": intervention.id, "statut": intervention.statut, "terminee_le": intervention.terminee_le}
