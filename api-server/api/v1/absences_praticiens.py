"""Bloc 3 — indisponibilités praticiens et réaffectations explicites."""
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from config import WA_TEMPLATES
from middleware.clinic_rbac import require_role
from models.database import AbsencePraticien, Patient, RendezVous, ReaffectationRdv, RoleEnum, StatutRDV, Utilisateur
from services.branding import get_branding_context
from services.whatsapp_service import send_whatsapp_message

logger = logging.getLogger("absences_praticiens")

router = APIRouter(prefix="/agenda", tags=["absences-praticiens"])
ROLES_GESTION = (RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)
ROLES_PRATICIENS = (RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.PRESTATAIRE)


class AbsenceCreate(BaseModel):
    praticien_id: int
    debut: datetime
    fin: datetime
    motif: Optional[str] = Field(None, max_length=300)


def _duration(rdv: RendezVous) -> timedelta:
    return (rdv.date_heure_fin - rdv.date_heure_debut) if rdv.date_heure_fin else timedelta(minutes=30)


async def _candidate_for(db: AsyncSession, rdv: RendezVous, clinic_id: int) -> Optional[int]:
    staff = (await db.execute(select(Utilisateur).where(
        Utilisateur.clinic_id == clinic_id,
        Utilisateur.is_active.is_(True),
        Utilisateur.role.in_([r.value for r in ROLES_PRATICIENS]),
        Utilisateur.id != rdv.praticien_id,
    ).order_by(Utilisateur.id))).scalars().all()
    end = rdv.date_heure_debut + _duration(rdv)
    for candidate in staff:
        conflict = await db.scalar(select(RendezVous.id).where(
            RendezVous.clinic_id == clinic_id,
            RendezVous.praticien_id == candidate.id,
            RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]),
            RendezVous.date_heure_debut < end,
            or_(RendezVous.date_heure_fin.is_(None), RendezVous.date_heure_fin > rdv.date_heure_debut),
        ).limit(1))
        if conflict is None:
            return candidate.id
    return None


@router.post("/absences-praticiens", status_code=201)
async def create_absence(
    payload: AbsenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_GESTION)),
):
    if payload.fin <= payload.debut:
        raise HTTPException(status_code=422, detail="La fin doit être postérieure au début")
    clinic_id = current_user["clinic_id"]
    practitioner = await db.scalar(select(Utilisateur).where(
        Utilisateur.id == payload.praticien_id,
        Utilisateur.clinic_id == clinic_id,
        Utilisateur.is_active.is_(True),
    ))
    if not practitioner:
        raise HTTPException(status_code=404, detail="Praticien introuvable ou inactif")
    absence = AbsencePraticien(clinic_id=clinic_id, praticien_id=payload.praticien_id,
                               debut=payload.debut, fin=payload.fin, motif=payload.motif,
                               created_by=int(current_user["id"]))
    db.add(absence)
    await db.flush()
    rdvs = (await db.execute(select(RendezVous).where(
        RendezVous.clinic_id == clinic_id,
        RendezVous.praticien_id == payload.praticien_id,
        RendezVous.date_heure_debut < payload.fin,
        or_(RendezVous.date_heure_fin.is_(None), RendezVous.date_heure_fin > payload.debut),
        RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]),
    ).order_by(RendezVous.date_heure_debut))).scalars().all()
    proposals = []
    for rdv in rdvs:
        proposed = await _candidate_for(db, rdv, clinic_id)
        item = ReaffectationRdv(clinic_id=clinic_id, absence_id=absence.id, rdv_id=rdv.id,
                                ancien_praticien_id=rdv.praticien_id,
                                praticien_propose_id=proposed, statut="a_valider" if proposed else "sans_proposition")
        db.add(item)
        proposals.append({"rdv_id": rdv.id, "praticien_propose_id": proposed, "statut": item.statut})
    await db.flush()
    return {"absence_id": absence.id, "rdvs_concernes": len(rdvs), "propositions": proposals}


@router.get("/absences-praticiens")
async def list_absences(db: AsyncSession = Depends(get_db), current_user=Depends(require_role(*ROLES_GESTION))):
    rows = (await db.execute(select(AbsencePraticien).where(
        AbsencePraticien.clinic_id == current_user["clinic_id"]
    ).order_by(AbsencePraticien.debut.desc()))).scalars().all()
    result = []
    for absence in rows:
        proposals = (await db.execute(select(ReaffectationRdv).where(
            ReaffectationRdv.absence_id == absence.id,
            ReaffectationRdv.clinic_id == current_user["clinic_id"],
        ))).scalars().all()
        result.append({"id": absence.id, "praticien_id": absence.praticien_id, "debut": absence.debut,
                       "fin": absence.fin, "motif": absence.motif, "statut": absence.statut,
                       "propositions": [{"id": p.id, "rdv_id": p.rdv_id, "praticien_propose_id": p.praticien_propose_id,
                                         "statut": p.statut} for p in proposals]})
    return result


@router.post("/absences-praticiens/{absence_id}/reaffectations/{reaffectation_id}/valider")
async def validate_reaffectation(
    absence_id: int,
    reaffectation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_GESTION)),
):
    item = await db.scalar(select(ReaffectationRdv).where(
        ReaffectationRdv.id == reaffectation_id,
        ReaffectationRdv.absence_id == absence_id,
        ReaffectationRdv.clinic_id == current_user["clinic_id"],
    ))
    if not item or not item.praticien_propose_id:
        raise HTTPException(status_code=404, detail="Proposition introuvable")
    rdv = await db.scalar(select(RendezVous).where(
        RendezVous.id == item.rdv_id, RendezVous.clinic_id == current_user["clinic_id"]
    ))
    if not rdv:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    end = rdv.date_heure_debut + _duration(rdv)
    conflict = await db.scalar(select(RendezVous.id).where(
        RendezVous.id != rdv.id, RendezVous.clinic_id == rdv.clinic_id,
        RendezVous.praticien_id == item.praticien_propose_id,
        RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]),
        RendezVous.date_heure_debut < end,
        or_(RendezVous.date_heure_fin.is_(None), RendezVous.date_heure_fin > rdv.date_heure_debut),
    ).limit(1))
    if conflict:
        raise HTTPException(status_code=409, detail="Le praticien proposé est désormais occupé")
    rdv.praticien_id = item.praticien_propose_id
    item.statut = "validee"
    item.valide_par = int(current_user["id"])
    item.valide_at = datetime.utcnow()
    await db.flush()

    # Notification WhatsApp au patient concerné — non bloquante : une
    # clinique sans WhatsApp configuré ou un patient sans numéro/opted_out
    # ne doit jamais empêcher la réaffectation elle-même.
    try:
        patient = await db.scalar(select(Patient).where(
            Patient.id == rdv.patient_id, Patient.clinic_id == current_user["clinic_id"],
        ))
        nouveau_praticien = await db.scalar(select(Utilisateur).where(
            Utilisateur.id == item.praticien_propose_id, Utilisateur.clinic_id == current_user["clinic_id"],
        ))
        if patient and patient.whatsapp_phone and not patient.opted_out and nouveau_praticien:
            branding = await get_branding_context(db, clinic_id=current_user["clinic_id"])
            message = (
                f"{branding['clinic_name']} — "
                + WA_TEMPLATES["rdv_praticien_change"].format(
                    date=rdv.date_heure_debut.strftime("%d/%m/%Y"),
                    heure=rdv.date_heure_debut.strftime("%H:%M"),
                    praticien=f"{nouveau_praticien.prenom} {nouveau_praticien.nom}",
                )
            )
            result = await send_whatsapp_message(patient.whatsapp_phone, message)
            if result.get("status") == "dev_mode":
                logger.warning(
                    f"Notification réaffectation non envoyée (WhatsApp non configuré) : rdv_id={rdv.id}"
                )
    except Exception:
        logger.exception(f"Échec notification WhatsApp après réaffectation rdv_id={rdv.id}")

    return {"message": "Réaffectation validée", "rdv_id": rdv.id, "praticien_id": rdv.praticien_id}
