"""
AutoCommerce Clinic — API Agenda
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from models.database import (
    RendezVous, Patient, Utilisateur, ActeMedical, Consentement, StatutRDV,
)
from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum

from services.agenda import get_disponibilites, creer_rdv, annuler_rdv
from services.remplacement_rdv import proposer_creneaux_apres_annulation
from services.parcours_arrivee import snapshot_rdv, journaliser_evenement, EVENEMENT_REPORT, EVENEMENT_ANNULATION

router = APIRouter(prefix="/agenda", tags=["agenda"])

CLINICAL_SELF_SCOPED_ROLES = {RoleEnum.MEDECIN.value, RoleEnum.ESTHETICIENNE.value}


def _is_self_scoped_practitioner(current_user: dict) -> bool:
    return current_user.get("role") in CLINICAL_SELF_SCOPED_ROLES


def _ensure_own_rdv(rdv: RendezVous, current_user: dict) -> None:
    if _is_self_scoped_practitioner(current_user) and rdv.praticien_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Ce rendez-vous est hors de votre périmètre")


# ── Schémas ────────────────────────────────────────────────

class RDVCreate(BaseModel):
    patient_id: int
    praticien_id: int
    acte_id: int
    date_heure: str  # ISO datetime
    salle: Optional[str] = Field(None, max_length=50)


class RDVUpdate(BaseModel):
    statut: Optional[str] = None
    notes_pre_acte: Optional[str] = None
    notes_post_acte: Optional[str] = None

    @field_validator("statut")
    @classmethod
    def statut_doit_etre_valide(cls, v):
        if v is not None:
            valeurs = [s.value for s in StatutRDV]
            if v not in valeurs:
                raise ValueError(f"statut invalide, doit être l'un de : {', '.join(valeurs)}")
        return v


class RDVReplanification(BaseModel):
    date_heure: str
    praticien_id: Optional[int] = None
    salle: Optional[str] = Field(None, max_length=50)


class RDVOut(BaseModel):
    id: int
    patient_id: int
    patient_nom: str
    praticien_id: int
    praticien_nom: str
    acte_id: Optional[int]
    acte_nom: Optional[str]
    date_heure_debut: str
    date_heure_fin: Optional[str]
    salle: Optional[str]
    statut: str
    consentement_manquant: bool = False
    consentement_id: Optional[int] = None

    class Config:
        from_attributes = True


# ── Routes ─────────────────────────────────────────────────

AGENDA_PRACTITIONER_ROLES = (
    RoleEnum.MEDECIN,
    RoleEnum.ESTHETICIENNE,
    RoleEnum.PRESTATAIRE,
)


@router.get("/praticiens")
async def list_agenda_praticiens(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE,
        RoleEnum.MEDECIN,
        RoleEnum.ESTHETICIENNE,
        RoleEnum.PRESTATAIRE,
        RoleEnum.ASSISTANTE,
        RoleEnum.ADMIN,
    )),
):
    """Liste interne des praticiens actifs, sans filtre de publication web."""
    result = await db.execute(
        select(Utilisateur)
        .where(
            Utilisateur.clinic_id == current_user["clinic_id"],
            Utilisateur.is_active.is_(True),
            Utilisateur.role.in_(AGENDA_PRACTITIONER_ROLES),
        )
        .order_by(Utilisateur.prenom, Utilisateur.nom)
    )
    return [
        {
            "id": praticien.id,
            "nom": praticien.nom,
            "prenom": praticien.prenom,
            "nom_complet": f"{praticien.prenom} {praticien.nom}",
            "specialite": praticien.specialite,
            "agenda_color": praticien.agenda_color,
        }
        for praticien in result.scalars().all()
    ]


@router.get("/actes")
async def list_agenda_actes(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(
        RoleEnum.DIRECTRICE,
        RoleEnum.MEDECIN,
        RoleEnum.ESTHETICIENNE,
        RoleEnum.PRESTATAIRE,
        RoleEnum.ASSISTANTE,
        RoleEnum.ADMIN,
    )),
):
    """Liste interne des actes actifs, indépendamment de leur publication web."""
    result = await db.execute(
        select(ActeMedical)
        .where(
            ActeMedical.clinic_id == current_user["clinic_id"],
            ActeMedical.is_active.is_(True),
        )
        .order_by(ActeMedical.nom)
    )
    return [
        {
            "id": acte.id,
            "nom": acte.nom,
            "categorie": acte.categorie,
            "duree_minutes": acte.duree_minutes,
            "description": acte.description,
            "prix_base": float(acte.prix_base) if acte.prix_base is not None else None,
        }
        for acte in result.scalars().all()
    ]

@router.get("", response_model=List[RDVOut])
async def list_agenda(
    praticien_id: Optional[int] = Query(None),
    date_debut: Optional[str] = Query(None),
    date_fin: Optional[str] = Query(None),
    patient_search: Optional[str] = Query(None, max_length=120),
    heure: Optional[str] = Query(None, pattern=r"^([01]\\d|2[0-3]):[0-5]\\d$"),
    vue: str = Query("semaine", pattern="^(semaine|jour)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Liste les RDV (vue semaine ou jour)."""
    query = select(RendezVous, Patient, Utilisateur, ActeMedical).join(
        Patient, RendezVous.patient_id == Patient.id
    ).join(
        Utilisateur, RendezVous.praticien_id == Utilisateur.id
    ).outerjoin(
        ActeMedical, RendezVous.acte_id == ActeMedical.id
    ).where(RendezVous.clinic_id == current_user["clinic_id"])

    if _is_self_scoped_practitioner(current_user):
        query = query.where(RendezVous.praticien_id == current_user["id"])
    elif praticien_id:
        query = query.where(RendezVous.praticien_id == praticien_id)

    if date_debut:
        dt_debut = datetime.fromisoformat(date_debut)
        query = query.where(RendezVous.date_heure_debut >= dt_debut)

    if date_fin:
        dt_fin = datetime.fromisoformat(date_fin)
        query = query.where(RendezVous.date_heure_debut <= dt_fin)

    if patient_search and patient_search.strip():
        needle = f"%{patient_search.strip()}%"
        query = query.where(or_(
            Patient.nom.ilike(needle),
            Patient.prenom.ilike(needle),
            Patient.telephone.ilike(needle),
            Patient.email.ilike(needle),
            Patient.adresse.ilike(needle),
            Patient.ville.ilike(needle),
        ))

    if heure:
        try:
            base_date = (date_debut or date_fin or datetime.utcnow().isoformat())[:10]
            start = datetime.fromisoformat(f"{base_date}T{heure}:00")
            end = start.replace(second=59)
            query = query.where(
                RendezVous.date_heure_debut >= start,
                RendezVous.date_heure_debut <= end,
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Format d'heure invalide, attendu HH:MM")

    query = query.order_by(RendezVous.date_heure_debut)
    result = await db.execute(query)

    rdvs = []
    for rdv, patient, praticien, acte in result.all():
        from services.consentement import verify_consent
        consent_missing = not await verify_consent(
            rdv.patient_id,
            rdv.acte_id,
            db,
            clinic_id=current_user["clinic_id"],
        )
        consent_result = await db.execute(
            select(Consentement.id)
            .where(
                Consentement.patient_id == rdv.patient_id,
                Consentement.clinic_id == current_user["clinic_id"],
                Consentement.est_valide.is_(True),
                *( [Consentement.acte_id == rdv.acte_id] if rdv.acte_id is not None else [] ),
            )
            .order_by(Consentement.signe_le.desc())
            .limit(1)
        )
        consentement_id = consent_result.scalar_one_or_none()

        rdvs.append(RDVOut(
            id=rdv.id,
            patient_id=rdv.patient_id,
            patient_nom=f"{patient.prenom} {patient.nom}",
            praticien_id=rdv.praticien_id,
            praticien_nom=f"{praticien.prenom} {praticien.nom}",
            acte_id=rdv.acte_id,
            acte_nom=acte.nom if acte else None,
            date_heure_debut=rdv.date_heure_debut.isoformat(),
            date_heure_fin=rdv.date_heure_fin.isoformat() if rdv.date_heure_fin else None,
            salle=rdv.salle,
            statut=rdv.statut,
            consentement_manquant=consent_missing,
            consentement_id=consentement_id,
        ))

    return rdvs


@router.post("/rdv", response_model=RDVOut)
async def create_rdv(
    data: RDVCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ADMIN)),
):
    """Crée un rendez-vous."""
    if _is_self_scoped_practitioner(current_user) and data.praticien_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Un praticien ne peut créer un rendez-vous que pour lui-même")
    try:
        date_heure = datetime.fromisoformat(data.date_heure)
        rdv, consent_missing = await creer_rdv(
            patient_id=data.patient_id,
            praticien_id=data.praticien_id,
            acte_id=data.acte_id,
            date_heure=date_heure,
            salle=data.salle,
            db=db,
            created_by=current_user["id"],
            clinic_id=current_user["clinic_id"],
        )

        # Récupérer noms
        patient_r = await db.execute(select(Patient).where(
            Patient.id == data.patient_id,
            Patient.clinic_id == current_user["clinic_id"],
        ))
        patient = patient_r.scalar_one()
        praticien_r = await db.execute(select(Utilisateur).where(
            Utilisateur.id == data.praticien_id,
            Utilisateur.clinic_id == current_user["clinic_id"],
        ))
        praticien = praticien_r.scalar_one()
        acte_r = await db.execute(select(ActeMedical).where(
            ActeMedical.id == data.acte_id,
            ActeMedical.clinic_id == current_user["clinic_id"],
        ))
        acte = acte_r.scalar_one()

        return RDVOut(
            id=rdv.id,
            patient_id=rdv.patient_id,
            patient_nom=f"{patient.prenom} {patient.nom}",
            praticien_id=rdv.praticien_id,
            praticien_nom=f"{praticien.prenom} {praticien.nom}",
            acte_id=rdv.acte_id,
            acte_nom=acte.nom,
            date_heure_debut=rdv.date_heure_debut.isoformat(),
            date_heure_fin=rdv.date_heure_fin.isoformat() if rdv.date_heure_fin else None,
            salle=rdv.salle,
            statut=rdv.statut,
            consentement_manquant=consent_missing,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/rdv/{rdv_id}/suggestions")
async def suggest_replanification(
    rdv_id: int,
    date: str = Query(..., description="YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ADMIN)),
):
    """Retourne des créneaux disponibles et explicables pour assister une replanification."""
    result = await db.execute(select(RendezVous).where(
        RendezVous.id == rdv_id,
        RendezVous.clinic_id == current_user["clinic_id"],
    ))
    rdv = result.scalar_one_or_none()
    if not rdv:
        raise HTTPException(status_code=404, detail="RDV non trouvé")
    _ensure_own_rdv(rdv, current_user)
    duration = max(15, int((rdv.date_heure_fin - rdv.date_heure_debut).total_seconds() / 60)) if rdv.date_heure_fin else 30
    slots = await get_disponibilites(rdv.praticien_id, datetime.strptime(date, "%Y-%m-%d").date(), duration, db, clinic_id=current_user["clinic_id"])
    return {
        "rdv_id": rdv_id,
        "date": date,
        "suggestions": [
            {"datetime": slot.get("datetime", slot) if isinstance(slot, dict) else slot, "score": max(50, 100 - index * 10), "reason": "Praticien disponible, durée suffisante et aucun chevauchement détecté."}
            for index, slot in enumerate(slots[:5])
        ],
    }


@router.patch("/rdv/{rdv_id}/replanifier")
async def reschedule_rdv(
    rdv_id: int,
    data: RDVReplanification,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ADMIN)),
):
    """Déplace un rendez-vous après contrôle des conflits de praticien et de salle."""
    try:
        new_start = datetime.fromisoformat(data.date_heure)
    except ValueError:
        raise HTTPException(status_code=400, detail="Format de date invalide")

    result = await db.execute(select(RendezVous).where(
        RendezVous.id == rdv_id,
        RendezVous.clinic_id == current_user["clinic_id"],
    ))
    rdv = result.scalar_one_or_none()
    if not rdv:
        raise HTTPException(status_code=404, detail="RDV non trouvé")
    _ensure_own_rdv(rdv, current_user)
    if rdv.statut in {StatutRDV.ANNULE.value, StatutRDV.TERMINE.value}:
        raise HTTPException(status_code=409, detail="Ce rendez-vous ne peut plus être replanifié")
    ancienne_valeur = snapshot_rdv(rdv)

    duration = max(15, int((rdv.date_heure_fin - rdv.date_heure_debut).total_seconds() / 60)) if rdv.date_heure_fin else 30
    new_end = new_start + timedelta(minutes=duration)
    target_praticien = data.praticien_id or rdv.praticien_id
    if _is_self_scoped_practitioner(current_user) and target_praticien != current_user["id"]:
        raise HTTPException(status_code=403, detail="Un praticien ne peut pas attribuer ce rendez-vous à un autre praticien")
    conflict_result = await db.execute(select(RendezVous).where(
        RendezVous.clinic_id == current_user["clinic_id"],
        RendezVous.id != rdv_id,
        RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]),
        RendezVous.date_heure_debut < new_end,
        RendezVous.date_heure_fin > new_start,
        or_(RendezVous.praticien_id == target_praticien, (RendezVous.salle == data.salle if data.salle else RendezVous.id == -1)),
    ))
    conflicts = conflict_result.scalars().all()
    if conflicts:
        raise HTTPException(status_code=409, detail="Conflit détecté avec un autre rendez-vous, praticien ou salle")

    rdv.date_heure_debut = new_start
    rdv.date_heure_fin = new_end
    if data.praticien_id:
        rdv.praticien_id = data.praticien_id
    if data.salle is not None:
        rdv.salle = data.salle or None
    await db.commit()
    await journaliser_evenement(
        db, rdv=rdv, type_evenement=EVENEMENT_REPORT,
        ancienne=ancienne_valeur, nouvelle=snapshot_rdv(rdv),
        auteur_id=int(current_user["id"]), motif="Rendez-vous replanifié",
    )
    return {"message": "Rendez-vous replanifié", "rdv_id": rdv_id, "date_heure_debut": new_start.isoformat(), "date_heure_fin": new_end.isoformat(), "salle": rdv.salle}


@router.patch("/rdv/{rdv_id}/statut")
@router.put("/rdv/{rdv_id}/statut")
async def update_rdv_statut(
    rdv_id: int,
    data: RDVUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ADMIN)),
):
    """Met à jour le statut d'un RDV."""
    result = await db.execute(select(RendezVous).where(
        RendezVous.id == rdv_id,
        RendezVous.clinic_id == current_user["clinic_id"],
    ))
    rdv = result.scalar_one_or_none()
    if not rdv:
        raise HTTPException(status_code=404, detail="RDV non trouvé")
    _ensure_own_rdv(rdv, current_user)

    if data.statut:
        rdv.statut = data.statut
    if data.notes_pre_acte is not None:
        rdv.notes_pre_acte = data.notes_pre_acte
    if data.notes_post_acte is not None:
        rdv.notes_post_acte = data.notes_post_acte

    await db.flush()
    return {"message": "RDV mis à jour"}


@router.delete("/rdv/{rdv_id}")
async def cancel_rdv_route(
    rdv_id: int,
    raison: Optional[str] = Query(None, min_length=3),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)),
):
    """Annule un RDV."""
    if raison is None:
        raison = "Annulation sans raison spécifiée (via API DELETE)"
    """Annule un RDV."""
    try:
        result = await db.execute(select(RendezVous).where(
            RendezVous.id == rdv_id, RendezVous.clinic_id == current_user["clinic_id"],
        ))
        rdv_avant = result.scalar_one_or_none()
        if not rdv_avant:
            raise HTTPException(status_code=404, detail="RDV non trouvé")
        _ensure_own_rdv(rdv_avant, current_user)
        ancienne_valeur = snapshot_rdv(rdv_avant)
        rdv = await annuler_rdv(
            rdv_id,
            raison,
            db,
            clinic_id=current_user["clinic_id"],
        )
        await journaliser_evenement(
            db, rdv=rdv, type_evenement=EVENEMENT_ANNULATION,
            ancienne=ancienne_valeur, nouvelle=snapshot_rdv(rdv),
            auteur_id=int(current_user["id"]), motif=raison,
        )
        suggestions = await proposer_creneaux_apres_annulation(db, rdv, clinic_id=current_user["clinic_id"])
        return {"message": "RDV annulé", "rdv_id": rdv.id, "suggestions": [
            {"id": item.id, "date_heure_debut": item.date_heure_debut, "date_heure_fin": item.date_heure_fin}
            for item in suggestions
        ]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/disponibilites/{praticien_id}")
async def get_dispos(
    praticien_id: int,
    date: str = Query(..., description="YYYY-MM-DD"),
    duree: int = Query(30, ge=15, le=240),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.MEDECIN, RoleEnum.ADMIN)),
):
    """Créneaux libres d'un praticien pour une date."""
    date_jour = datetime.strptime(date, "%Y-%m-%d").date()
    creneaux = await get_disponibilites(
        praticien_id,
        date_jour,
        duree,
        db,
        clinic_id=current_user["clinic_id"],
    )
    return {"praticien_id": praticien_id, "date": date, "creneaux": creneaux}
