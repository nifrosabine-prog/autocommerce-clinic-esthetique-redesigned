"""
AutoCommerce Clinic — Bloc 3 : Accueil des patients.

Page d'accueil de l'assistante + parcours d'arrivée :
  recherche par nom / téléphone / référence / rendez-vous / source,
  réservation Internet / WhatsApp / téléphone / manuel (modèle unique),
  arrivée → présence confirmée → accord d'examen (ouverture d'épisode),
  absence (historique conservé), remplacement (nouveau RDV sans écrasement),
  journal d'événements d'agenda.

La sécurité reste backend : toutes les routes sont gardées par
require_role (Bloc 2).
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.clinic_rbac import require_role
from models.database import RoleEnum
from services import parcours_arrivee
from services import replanification_patient

router = APIRouter(prefix="/accueil", tags=["accueil"])

ROLES_ACCUEIL = (RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE, RoleEnum.ADMIN)
ROLES_LECTURE = (
    RoleEnum.DIRECTRICE, RoleEnum.MEDECIN, RoleEnum.ESTHETICIENNE,
    RoleEnum.ASSISTANTE, RoleEnum.ADMIN,
)


# ── Schémas ────────────────────────────────────────────────

class ReservationCreate(BaseModel):
    """Réservation unifiée : internet, whatsapp, telephone ou manuel."""
    source: str = Field(..., min_length=1, max_length=20)
    nom: str = Field(..., min_length=1, max_length=100)
    prenom: str = Field(..., min_length=1, max_length=100)
    telephone: str = Field(..., min_length=5, max_length=20)
    acte_id: int
    praticien_id: int
    date_heure: str  # ISO datetime
    email: Optional[str] = None
    salle: Optional[str] = Field(None, max_length=50)
    patient_id: Optional[int] = None
    motif: Optional[str] = Field(None, max_length=500)


class AbsenceRequest(BaseModel):
    motif: str = Field(..., min_length=3, max_length=500)


class RemplacementRequest(BaseModel):
    nouveau_patient_id: int
    motif: str = Field(..., min_length=3, max_length=500)


class ReplanificationPropositionRequest(BaseModel):
    dates: list[str] = Field(..., min_length=1, max_length=7)


class ReplanificationConfirmationRequest(BaseModel):
    date_heure: str = Field(..., min_length=10, max_length=40)
    confirmation_source: str = Field(default="whatsapp", min_length=2, max_length=30)


# ── Routes ─────────────────────────────────────────────────

@router.get("")
async def liste_accueil(
    q: Optional[str] = Query(None, max_length=120, description="nom, téléphone, référence, id RDV"),
    source: Optional[str] = Query(None, pattern="^(internet|whatsapp|telephone|manuel)$"),
    date_debut: Optional[str] = Query(None, description="ISO datetime"),
    date_fin: Optional[str] = Query(None, description="ISO datetime"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_LECTURE)),
):
    """Page « Accueil des patients » : recherche multi-critères."""
    try:
        return await parcours_arrivee.lister_accueil(
            db, current_user,
            q=q, source=source, date_debut=date_debut, date_fin=date_fin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/reservations", status_code=201)
async def creer_reservation(
    payload: ReservationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(RoleEnum.DIRECTRICE, RoleEnum.ASSISTANTE,
                                      RoleEnum.MEDECIN, RoleEnum.ADMIN)),
):
    """Crée une réservation (modèle unique, toute source)."""
    try:
        return await parcours_arrivee.creer_rdv_complet(
            db, current_user,
            source=payload.source,
            nom=payload.nom, prenom=payload.prenom, telephone=payload.telephone,
            email=payload.email, acte_id=payload.acte_id,
            praticien_id=payload.praticien_id,
            date_heure=payload.date_heure, salle=payload.salle,
            patient_id=payload.patient_id, motif=payload.motif,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/doublons")
async def detection_doublons(
    telephone: Optional[str] = Query(None, max_length=20),
    nom: Optional[str] = Query(None, max_length=100),
    prenom: Optional[str] = Query(None, max_length=100),
    email: Optional[str] = Query(None, max_length=255),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_ACCUEIL)),
):
    """Détection de doublons patient/prospect avant création."""
    if not any([telephone, nom, prenom, email]):
        raise HTTPException(status_code=400, detail="Au moins un critère requis")
    return await parcours_arrivee.rechercher_doublons(
        db, clinic_id=current_user["clinic_id"],
        telephone=telephone, nom=nom, prenom=prenom, email=email,
    )


@router.post("/rdv/{rdv_id}/arrivee")
async def patient_arrive(
    rdv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_ACCUEIL)),
):
    """Patient arrivé à l'accueil."""
    try:
        return await parcours_arrivee.confirmer_arrivee(db, current_user, rdv_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/rdv/{rdv_id}/presence")
async def presence_confirmee(
    rdv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_ACCUEIL)),
):
    """Présence confirmée (prérequis : arrivé)."""
    try:
        return await parcours_arrivee.confirmer_presence(db, current_user, rdv_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/rdv/{rdv_id}/accord")
async def accord_examen(
    rdv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_ACCUEIL)),
):
    """Accord pour être reçu / examiné + ouverture de l'épisode patient."""
    try:
        return await parcours_arrivee.confirmer_accord(db, current_user, rdv_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/rdv/{rdv_id}/absence")
async def absence_patient(
    rdv_id: int,
    payload: AbsenceRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_ACCUEIL)),
):
    """Patient absent : le rendez-vous est conservé (no_show), historique intact."""
    try:
        return await parcours_arrivee.declarer_absence(db, current_user, rdv_id, payload.motif)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/rdv/{rdv_id}/replanification/proposer")
async def proposer_replanification_patient(
    rdv_id: int,
    payload: ReplanificationPropositionRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_ACCUEIL)),
):
    """Prépare des créneaux et un brouillon WhatsApp sans envoi automatique."""
    try:
        return await replanification_patient.proposer_replanification(
            db, rdv_id, clinic_id=current_user["clinic_id"],
            created_by=int(current_user["id"]), dates=payload.dates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/rdv/{rdv_id}/replanification/confirmer", status_code=201)
async def confirmer_replanification_patient(
    rdv_id: int,
    payload: ReplanificationConfirmationRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_ACCUEIL)),
):
    """Crée le nouveau RDV après confirmation explicite du patient."""
    try:
        return await replanification_patient.confirmer_replanification(
            db, rdv_id, date_heure=payload.date_heure,
            clinic_id=current_user["clinic_id"], confirmed_by=int(current_user["id"]),
            confirmation_source=payload.confirmation_source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/rdv/{rdv_id}/remplacement", status_code=201)
async def remplacement_patient(
    rdv_id: int,
    payload: RemplacementRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_ACCUEIL)),
):
    """Remplacement après absence : nouveau RDV, l'ancien n'est jamais écrasé."""
    try:
        return await parcours_arrivee.remplacer_rdv(
            db, current_user, rdv_id,
            nouveau_patient_id=payload.nouveau_patient_id, motif=payload.motif,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/rdv/{rdv_id}/evenements")
async def historique_rdv(
    rdv_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(*ROLES_LECTURE)),
):
    """Journal complet des événements du rendez-vous (ancienne/nouvelle valeur, auteur, date, motif)."""
    try:
        return await parcours_arrivee.evenements_rdv(db, rdv_id, current_user["clinic_id"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
