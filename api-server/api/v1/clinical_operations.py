"""Opérations cliniques v2 : cures, séances, suivis et sécurité patient."""
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from models.database import (
    ActeMedical,
    CureTraitement,
    DossierMedical,
    EvenementIndesirable,
    Patient,
    ProtocoleSoin,
    RendezVous,
    SeanceCure,
    SuiviPostActe,
    Utilisateur,
)
from services.access_control import clinic_id_for

router = APIRouter(prefix="/clinical-ops", tags=["clinical-operations"])

CLINICAL_ROLES = {"directrice", "medecin", "estheticienne", "assistante", "admin"}
MANAGE_ROLES = {"directrice", "medecin", "admin"}


def _role(user: dict) -> str:
    return str(user.get("role", "")).replace("RoleEnum.", "").lower()


def _require_role(user: dict, roles: set[str]) -> int:
    if _role(user) not in roles:
        raise HTTPException(status_code=403, detail="Accès refusé pour ce rôle")
    try:
        return clinic_id_for(user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Contexte clinique obligatoire") from exc


def _dt(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


class CureCreate(BaseModel):
    patient_id: int
    acte_id: Optional[int] = None
    nom: str = Field(min_length=2, max_length=200)
    description: Optional[str] = Field(default=None, max_length=4000)
    zone_anatomique: Optional[str] = Field(default=None, max_length=100)
    seances_prevues: int = Field(ge=1, le=100)
    premiere_seance_at: Optional[datetime] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class SeanceCreate(BaseModel):
    numero: int = Field(ge=1, le=100)
    rendez_vous_id: Optional[int] = None
    dossier_id: Optional[int] = None
    praticien_id: Optional[int] = None
    planifiee_at: Optional[datetime] = None
    zone_anatomique: Optional[str] = Field(default=None, max_length=100)
    produits_lots: Optional[list[dict]] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    suivi_recommande_le: Optional[date] = None


class SeanceStatusPatch(BaseModel):
    statut: str = Field(pattern="^(a_venir|planifiee|realisee|annulee|reportee)$")
    realisee_at: Optional[datetime] = None
    dossier_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class SuiviCreate(BaseModel):
    patient_id: int
    dossier_id: Optional[int] = None
    seance_id: Optional[int] = None
    type_suivi: str = Field(default="controle_post_acte", min_length=2, max_length=60)
    echeance_at: datetime
    assigne_a_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class SuiviPatch(BaseModel):
    statut: str = Field(pattern="^(a_faire|en_cours|termine|annule)$")
    notes: Optional[str] = Field(default=None, max_length=4000)


class EvenementCreate(BaseModel):
    patient_id: int
    dossier_id: Optional[int] = None
    acte_id: Optional[int] = None
    seance_id: Optional[int] = None
    survenu_at: datetime
    zone_anatomique: Optional[str] = Field(default=None, max_length=100)
    description: str = Field(min_length=5, max_length=10000)
    gravite: str = Field(default="faible", pattern="^(faible|moderee|elevee|critique)$")
    action_effectuee: Optional[str] = Field(default=None, max_length=10000)
    praticien_informe: bool = False
    suivi: Optional[str] = Field(default=None, max_length=10000)


class EvenementPatch(BaseModel):
    statut: str = Field(pattern="^(ouvert|surveille|cloture)$")
    action_effectuee: Optional[str] = Field(default=None, max_length=10000)
    praticien_informe: Optional[bool] = None
    suivi: Optional[str] = Field(default=None, max_length=10000)


class ProtocolCreate(BaseModel):
    acte_id: Optional[int] = None
    nom: str = Field(min_length=2, max_length=200)
    categorie: str = Field(default="esthetique", min_length=2, max_length=80)
    version: str = Field(default="1.0", min_length=1, max_length=30)
    etapes_avant: list[str] = Field(default_factory=list, max_length=50)
    etapes_pendant: list[str] = Field(default_factory=list, max_length=50)
    etapes_apres: list[str] = Field(default_factory=list, max_length=50)


def _patient_query(patient_id: int, clinic_id: int):
    return select(Patient).where(
        Patient.id == patient_id,
        Patient.clinic_id == clinic_id,
        Patient.anonymized_at.is_(None),
    )


async def _ensure_patient(db: AsyncSession, patient_id: int, clinic_id: int) -> Patient:
    patient = await db.scalar(_patient_query(patient_id, clinic_id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient introuvable dans cette clinique")
    return patient


def _serialize_cure(cure: CureTraitement, sessions: list[SeanceCure]) -> dict:
    done = sum(1 for session in sessions if session.statut == "realisee")
    return {
        "id": cure.id,
        "clinic_id": cure.clinic_id,
        "patient_id": cure.patient_id,
        "acte_id": cure.acte_id,
        "nom": cure.nom,
        "description": cure.description,
        "zone_anatomique": cure.zone_anatomique,
        "seances_prevues": cure.seances_prevues,
        "seances_realisees": done,
        "seances_restantes": max(cure.seances_prevues - done, 0),
        "statut": cure.statut,
        "prochaine_seance_at": _dt(cure.prochaine_seance_at),
        "notes": cure.notes,
        "created_at": _dt(cure.created_at),
        "seances": [
            {
                "id": item.id,
                "numero": item.numero,
                "rendez_vous_id": item.rendez_vous_id,
                "dossier_id": item.dossier_id,
                "praticien_id": item.praticien_id,
                "planifiee_at": _dt(item.planifiee_at),
                "realisee_at": _dt(item.realisee_at),
                "statut": item.statut,
                "zone_anatomique": item.zone_anatomique,
                "produits_lots": item.produits_lots or [],
                "photos_ids": item.photos_ids or [],
                "notes": item.notes,
                "suivi_recommande_le": item.suivi_recommande_le.isoformat() if item.suivi_recommande_le else None,
            }
            for item in sorted(sessions, key=lambda x: x.numero)
        ],
    }


async def _get_cure(db: AsyncSession, cure_id: int, clinic_id: int) -> CureTraitement:
    cure = await db.scalar(
        select(CureTraitement).where(
            CureTraitement.id == cure_id,
            CureTraitement.clinic_id == clinic_id,
        )
    )
    if not cure:
        raise HTTPException(status_code=404, detail="Cure introuvable")
    return cure


async def _get_cure_payload(db: AsyncSession, cure_id: int, clinic_id: int) -> dict:
    cure = await _get_cure(db, cure_id, clinic_id)
    sessions = (await db.execute(select(SeanceCure).where(
        SeanceCure.cure_id == cure.id,
        SeanceCure.clinic_id == clinic_id,
    ).order_by(SeanceCure.numero))).scalars().all()
    return _serialize_cure(cure, list(sessions))


async def _sync_cure(db: AsyncSession, cure: CureTraitement, clinic_id: int) -> None:
    sessions = (await db.execute(select(SeanceCure).where(
        SeanceCure.cure_id == cure.id,
        SeanceCure.clinic_id == clinic_id,
    ).order_by(SeanceCure.planifiee_at))).scalars().all()
    done = sum(1 for item in sessions if item.statut == "realisee")
    pending = [item for item in sessions if item.statut in {"a_venir", "planifiee", "reportee"} and item.planifiee_at]
    cure.prochaine_seance_at = pending[0].planifiee_at if pending else None
    if cure.statut not in {"annulee", "terminee"}:
        cure.statut = "terminee" if done >= cure.seances_prevues else "active"


@router.get("/dashboard")
async def clinical_dashboard(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, CLINICAL_ROLES)
    now = datetime.utcnow()
    week_end = now + timedelta(days=7)
    followups = (await db.execute(select(SuiviPostActe).where(
        SuiviPostActe.clinic_id == clinic_id,
        SuiviPostActe.statut.in_(["a_faire", "en_cours"]),
        SuiviPostActe.echeance_at <= week_end,
    ).order_by(SuiviPostActe.echeance_at))).scalars().all()
    events = (await db.execute(select(EvenementIndesirable).where(
        EvenementIndesirable.clinic_id == clinic_id,
        EvenementIndesirable.statut != "cloture",
    ).order_by(EvenementIndesirable.gravite.desc(), EvenementIndesirable.survenu_at.desc()))).scalars().all()
    active_cures = await db.scalar(select(func.count(CureTraitement.id)).where(
        CureTraitement.clinic_id == clinic_id,
        CureTraitement.statut == "active",
    ))
    today = now.date()
    return {
        "suivis": {
            "aujourd_hui": sum(1 for item in followups if item.echeance_at.date() <= today),
            "cette_semaine": len(followups),
            "items": [
                {"id": item.id, "patient_id": item.patient_id, "type_suivi": item.type_suivi,
                 "echeance_at": _dt(item.echeance_at), "statut": item.statut, "notes": item.notes}
                for item in followups[:20]
            ],
        },
        "evenements_indesirables": {
            "ouverts": len(events),
            "critiques": sum(1 for item in events if item.gravite == "critique"),
            "items": [
                {"id": item.id, "patient_id": item.patient_id, "gravite": item.gravite,
                 "statut": item.statut, "survenu_at": _dt(item.survenu_at), "description": item.description[:180]}
                for item in events[:20]
            ],
        },
        "cures_actives": int(active_cures or 0),
    }


@router.get("/cures")
async def list_cures(
    patient_id: Optional[int] = Query(None),
    statut: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, CLINICAL_ROLES)
    query = select(CureTraitement).where(CureTraitement.clinic_id == clinic_id)
    if patient_id is not None:
        query = query.where(CureTraitement.patient_id == patient_id)
    if statut:
        query = query.where(CureTraitement.statut == statut)
    cures = (await db.execute(query.order_by(CureTraitement.created_at.desc()))).scalars().all()
    payload = []
    for cure in cures:
        payload.append(await _get_cure_payload(db, cure.id, clinic_id))
    return payload


@router.post("/cures", status_code=status.HTTP_201_CREATED)
async def create_cure(
    payload: CureCreate,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, MANAGE_ROLES)
    await _ensure_patient(db, payload.patient_id, clinic_id)
    if payload.acte_id is not None and not await db.scalar(select(ActeMedical).where(
        ActeMedical.id == payload.acte_id, ActeMedical.clinic_id == clinic_id, ActeMedical.is_active,
    )):
        raise HTTPException(status_code=404, detail="Acte introuvable dans cette clinique")
    cure = CureTraitement(
        clinic_id=clinic_id, patient_id=payload.patient_id, acte_id=payload.acte_id,
        nom=payload.nom.strip(), description=payload.description, zone_anatomique=payload.zone_anatomique,
        seances_prevues=payload.seances_prevues, statut="active", prochaine_seance_at=payload.premiere_seance_at,
        notes=payload.notes, created_by=current_user["id"],
    )
    db.add(cure)
    await db.flush()
    start = payload.premiere_seance_at
    for number in range(1, payload.seances_prevues + 1):
        planned = start + timedelta(days=14 * (number - 1)) if start else None
        db.add(SeanceCure(
            clinic_id=clinic_id, cure_id=cure.id, numero=number,
            planifiee_at=planned, statut="planifiee" if planned else "a_venir",
            zone_anatomique=payload.zone_anatomique,
        ))
    await db.commit()
    return await _get_cure_payload(db, cure.id, clinic_id)


@router.post("/cures/{cure_id}/seances", status_code=status.HTTP_201_CREATED)
async def add_cure_session(
    cure_id: int,
    payload: SeanceCreate,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, MANAGE_ROLES)
    cure = await _get_cure(db, cure_id, clinic_id)
    if await db.scalar(select(SeanceCure).where(
        SeanceCure.cure_id == cure_id, SeanceCure.clinic_id == clinic_id, SeanceCure.numero == payload.numero,
    )):
        raise HTTPException(status_code=409, detail="Cette séance existe déjà")
    if payload.praticien_id is not None and not await db.scalar(select(Utilisateur).where(
        Utilisateur.id == payload.praticien_id, Utilisateur.clinic_id == clinic_id, Utilisateur.is_active,
    )):
        raise HTTPException(status_code=404, detail="Praticien introuvable dans cette clinique")
    if payload.rendez_vous_id is not None and not await db.scalar(select(RendezVous).where(
        RendezVous.id == payload.rendez_vous_id,
        RendezVous.clinic_id == clinic_id,
        RendezVous.patient_id == cure.patient_id,
    )):
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable pour ce patient")
    if payload.dossier_id is not None and not await db.scalar(select(DossierMedical).where(
        DossierMedical.id == payload.dossier_id,
        DossierMedical.clinic_id == clinic_id,
        DossierMedical.patient_id == cure.patient_id,
    )):
        raise HTTPException(status_code=404, detail="Dossier médical introuvable pour ce patient")
    session = SeanceCure(clinic_id=clinic_id, cure_id=cure.id, **payload.model_dump())
    if session.planifiee_at:
        session.statut = "planifiee"
    db.add(session)
    await _sync_cure(db, cure, clinic_id)
    await db.commit()
    return await _get_cure_payload(db, cure.id, clinic_id)


@router.patch("/cures/{cure_id}/seances/{seance_id}")
async def update_cure_session(
    cure_id: int,
    seance_id: int,
    payload: SeanceStatusPatch,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, MANAGE_ROLES)
    cure = await _get_cure(db, cure_id, clinic_id)
    session = await db.scalar(select(SeanceCure).where(
        SeanceCure.id == seance_id, SeanceCure.cure_id == cure.id, SeanceCure.clinic_id == clinic_id,
    ))
    if not session:
        raise HTTPException(status_code=404, detail="Séance introuvable")
    session.statut = payload.statut
    session.realisee_at = payload.realisee_at or (datetime.utcnow() if payload.statut == "realisee" else None)
    if payload.dossier_id is not None:
        if not await db.scalar(select(DossierMedical).where(
            DossierMedical.id == payload.dossier_id,
            DossierMedical.clinic_id == clinic_id,
            DossierMedical.patient_id == cure.patient_id,
        )):
            raise HTTPException(status_code=404, detail="Dossier médical introuvable pour ce patient")
        session.dossier_id = payload.dossier_id
    if payload.notes is not None:
        session.notes = payload.notes
    if session.statut == "realisee" and session.suivi_recommande_le:
        followup_exists = await db.scalar(select(SuiviPostActe).where(
            SuiviPostActe.clinic_id == clinic_id,
            SuiviPostActe.seance_id == session.id,
        ))
        if not followup_exists:
            db.add(SuiviPostActe(
                clinic_id=clinic_id,
                patient_id=cure.patient_id,
                seance_id=session.id,
                type_suivi="controle_post_acte",
                echeance_at=datetime.combine(session.suivi_recommande_le, datetime.min.time()),
                statut="a_faire",
                created_by=current_user["id"],
            ))
    await _sync_cure(db, cure, clinic_id)
    await db.commit()
    return await _get_cure_payload(db, cure.id, clinic_id)


@router.get("/suivis")
async def list_followups(
    statut: Optional[str] = Query(None),
    horizon_days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, CLINICAL_ROLES)
    query = select(SuiviPostActe).where(
        SuiviPostActe.clinic_id == clinic_id,
        SuiviPostActe.echeance_at <= datetime.utcnow() + timedelta(days=horizon_days),
    )
    if statut:
        query = query.where(SuiviPostActe.statut == statut)
    rows = (await db.execute(query.order_by(SuiviPostActe.echeance_at))).scalars().all()
    return [{"id": row.id, "patient_id": row.patient_id, "dossier_id": row.dossier_id,
             "seance_id": row.seance_id, "type_suivi": row.type_suivi, "echeance_at": _dt(row.echeance_at),
             "statut": row.statut, "assigne_a_id": row.assigne_a_id, "notes": row.notes,
             "termine_at": _dt(row.termine_at)} for row in rows]


@router.post("/suivis", status_code=status.HTTP_201_CREATED)
async def create_followup(
    payload: SuiviCreate,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, MANAGE_ROLES)
    await _ensure_patient(db, payload.patient_id, clinic_id)
    if payload.dossier_id is not None and not await db.scalar(select(DossierMedical).where(
        DossierMedical.id == payload.dossier_id,
        DossierMedical.clinic_id == clinic_id,
        DossierMedical.patient_id == payload.patient_id,
    )):
        raise HTTPException(status_code=404, detail="Dossier médical introuvable pour ce patient")
    if payload.seance_id is not None and not await db.scalar(
        select(SeanceCure)
        .join(CureTraitement, CureTraitement.id == SeanceCure.cure_id)
        .where(
            SeanceCure.id == payload.seance_id,
            SeanceCure.clinic_id == clinic_id,
            CureTraitement.clinic_id == clinic_id,
            CureTraitement.patient_id == payload.patient_id,
        )
    ):
        raise HTTPException(status_code=404, detail="Séance introuvable pour ce patient")
    if payload.assigne_a_id is not None and not await db.scalar(select(Utilisateur).where(
        Utilisateur.id == payload.assigne_a_id, Utilisateur.clinic_id == clinic_id, Utilisateur.is_active,
    )):
        raise HTTPException(status_code=404, detail="Utilisateur assigné introuvable")
    row = SuiviPostActe(clinic_id=clinic_id, created_by=current_user["id"], **payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "patient_id": row.patient_id, "echeance_at": _dt(row.echeance_at), "statut": row.statut}


@router.patch("/suivis/{suivi_id}")
async def update_followup(
    suivi_id: int,
    payload: SuiviPatch,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, CLINICAL_ROLES)
    row = await db.scalar(select(SuiviPostActe).where(
        SuiviPostActe.id == suivi_id, SuiviPostActe.clinic_id == clinic_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Suivi introuvable")
    row.statut = payload.statut
    if payload.notes is not None:
        row.notes = payload.notes
    row.termine_at = datetime.utcnow() if payload.statut == "termine" else None
    await db.commit()
    return {"id": row.id, "statut": row.statut, "termine_at": _dt(row.termine_at)}


@router.get("/evenements-indesirables")
async def list_adverse_events(
    statut: Optional[str] = Query(None),
    gravite: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, CLINICAL_ROLES)
    query = select(EvenementIndesirable).where(EvenementIndesirable.clinic_id == clinic_id)
    if statut:
        query = query.where(EvenementIndesirable.statut == statut)
    if gravite:
        query = query.where(EvenementIndesirable.gravite == gravite)
    rows = (await db.execute(query.order_by(EvenementIndesirable.survenu_at.desc()))).scalars().all()
    return [{"id": row.id, "patient_id": row.patient_id, "dossier_id": row.dossier_id,
             "acte_id": row.acte_id, "seance_id": row.seance_id, "survenu_at": _dt(row.survenu_at),
             "zone_anatomique": row.zone_anatomique, "description": row.description,
             "gravite": row.gravite, "action_effectuee": row.action_effectuee,
             "praticien_informe": row.praticien_informe, "suivi": row.suivi, "statut": row.statut}
            for row in rows]


@router.post("/evenements-indesirables", status_code=status.HTTP_201_CREATED)
async def create_adverse_event(
    payload: EvenementCreate,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, MANAGE_ROLES)
    await _ensure_patient(db, payload.patient_id, clinic_id)
    if payload.dossier_id is not None and not await db.scalar(select(DossierMedical).where(
        DossierMedical.id == payload.dossier_id,
        DossierMedical.clinic_id == clinic_id,
        DossierMedical.patient_id == payload.patient_id,
    )):
        raise HTTPException(status_code=404, detail="Dossier médical introuvable pour ce patient")
    if payload.seance_id is not None and not await db.scalar(
        select(SeanceCure)
        .join(CureTraitement, CureTraitement.id == SeanceCure.cure_id)
        .where(
            SeanceCure.id == payload.seance_id,
            SeanceCure.clinic_id == clinic_id,
            CureTraitement.clinic_id == clinic_id,
            CureTraitement.patient_id == payload.patient_id,
        )
    ):
        raise HTTPException(status_code=404, detail="Séance introuvable pour ce patient")
    if payload.acte_id is not None and not await db.scalar(select(ActeMedical).where(
        ActeMedical.id == payload.acte_id,
        ActeMedical.clinic_id == clinic_id,
        ActeMedical.is_active,
    )):
        raise HTTPException(status_code=404, detail="Acte introuvable dans cette clinique")
    row = EvenementIndesirable(clinic_id=clinic_id, created_by=current_user["id"], **payload.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "statut": row.statut, "gravite": row.gravite}


@router.patch("/evenements-indesirables/{event_id}")
async def update_adverse_event(
    event_id: int,
    payload: EvenementPatch,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, MANAGE_ROLES)
    row = await db.scalar(select(EvenementIndesirable).where(
        EvenementIndesirable.id == event_id, EvenementIndesirable.clinic_id == clinic_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Événement introuvable")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await db.commit()
    return {"id": row.id, "statut": row.statut, "gravite": row.gravite, "praticien_informe": row.praticien_informe}


@router.get("/protocoles")
async def list_protocols(
    actif: Optional[bool] = Query(None),
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, CLINICAL_ROLES)
    query = select(ProtocoleSoin).where(ProtocoleSoin.clinic_id == clinic_id)
    if actif is not None:
        query = query.where(ProtocoleSoin.actif == actif)
    rows = (await db.execute(query.order_by(ProtocoleSoin.nom, ProtocoleSoin.version.desc()))).scalars().all()
    return [{"id": row.id, "acte_id": row.acte_id, "nom": row.nom, "categorie": row.categorie,
             "version": row.version, "etapes_avant": row.etapes_avant or [],
             "etapes_pendant": row.etapes_pendant or [], "etapes_apres": row.etapes_apres or [],
             "actif": row.actif} for row in rows]


@router.post("/protocoles", status_code=status.HTTP_201_CREATED)
async def create_protocol(
    payload: ProtocolCreate,
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = _require_role(current_user, MANAGE_ROLES)
    if payload.acte_id is not None and not await db.scalar(select(ActeMedical).where(
        ActeMedical.id == payload.acte_id, ActeMedical.clinic_id == clinic_id, ActeMedical.is_active,
    )):
        raise HTTPException(status_code=404, detail="Acte introuvable dans cette clinique")
    existing = await db.scalar(select(ProtocoleSoin).where(
        ProtocoleSoin.clinic_id == clinic_id, ProtocoleSoin.nom == payload.nom.strip(), ProtocoleSoin.version == payload.version,
    ))
    if existing:
        raise HTTPException(status_code=409, detail="Cette version de protocole existe déjà")
    row = ProtocoleSoin(clinic_id=clinic_id, created_by=current_user["id"], **payload.model_dump())
    row.nom = row.nom.strip()
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "nom": row.nom, "version": row.version, "actif": row.actif}
