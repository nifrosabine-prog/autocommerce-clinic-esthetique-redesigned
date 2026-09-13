"""Workflow de replanification après absence patient.

Le moteur prépare des créneaux et un brouillon WhatsApp, puis la création du
nouveau rendez-vous n'est effectuée qu'après une confirmation explicite.
"""
from __future__ import annotations
from datetime import datetime
from typing import Iterable
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import RendezVous, Patient, StatutRDV
from models.security import TacheInterneAssistant, StatutTacheInterneEnum
from services.agenda import creer_rdv, get_disponibilites
from services.parcours_arrivee import journaliser_evenement, snapshot_rdv, EVENEMENT_CREATION


def _as_naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo else value


async def proposer_replanification(
    db: AsyncSession,
    rdv_id: int,
    *,
    clinic_id: int,
    created_by: int,
    dates: Iterable[str],
) -> dict:
    rdv = await db.scalar(select(RendezVous).where(
        RendezVous.id == rdv_id, RendezVous.clinic_id == clinic_id,
    ))
    if not rdv:
        raise ValueError("Rendez-vous introuvable")
    if rdv.statut != StatutRDV.NO_SHOW.value:
        raise ValueError("La replanification patient exige une absence confirmée")
    patient = await db.scalar(select(Patient).where(
        Patient.id == rdv.patient_id, Patient.clinic_id == clinic_id,
    ))
    duration = max(15, int((rdv.date_heure_fin - rdv.date_heure_debut).total_seconds() / 60)) if rdv.date_heure_fin else 30
    options = []
    seen = set()
    for raw_date in dates:
        day = datetime.strptime(raw_date, "%Y-%m-%d").date()
        for slot in await get_disponibilites(rdv.praticien_id, day, duration, db, clinic_id=clinic_id):
            dt = slot.get("datetime", slot) if isinstance(slot, dict) else slot
            if dt in seen:
                continue
            seen.add(dt)
            options.append({
                "datetime": dt,
                "score": max(50, 100 - len(options) * 10),
                "reason": "Créneau libre pour le même praticien et la même durée.",
            })
            if len(options) >= 3:
                break
        if len(options) >= 3:
            break
    if not options:
        raise ValueError("Aucun créneau disponible pour proposer une replanification")
    name = getattr(patient, "prenom", "Patient") if patient else "Patient"
    formatted = ", ".join(datetime.fromisoformat(o["datetime"]).strftime("%d/%m à %Hh%M") for o in options)
    draft = (
        f"Bonjour {name}, nous avons bien noté votre absence. "
        f"Souhaitez-vous reprogrammer votre rendez-vous sur l'un de ces créneaux : {formatted} ? "
        "Répondez avec le numéro ou la date choisie."
    )
    task = TacheInterneAssistant(
        clinic_id=clinic_id,
        creee_par_id=created_by,
        patient_id=rdv.patient_id,
        titre=f"Replanification WhatsApp à confirmer — RDV #{rdv.id}",
        description=f"Créneaux proposés : {formatted}\nBrouillon non envoyé : {draft}",
        priorite="normale",
        statut=StatutTacheInterneEnum.A_FAIRE.value,
    )
    db.add(task)
    await db.flush()
    return {"rdv_id": rdv.id, "patient_id": rdv.patient_id, "options": options, "whatsapp_draft": draft, "task_id": task.id, "requires_confirmation": True}


async def confirmer_replanification(
    db: AsyncSession,
    rdv_id: int,
    *,
    date_heure: str,
    clinic_id: int,
    confirmed_by: int,
    confirmation_source: str = "whatsapp",
) -> dict:
    rdv = await db.scalar(select(RendezVous).where(
        RendezVous.id == rdv_id, RendezVous.clinic_id == clinic_id,
    ).with_for_update())
    if not rdv:
        raise ValueError("Rendez-vous introuvable")
    if rdv.statut != StatutRDV.NO_SHOW.value:
        raise ValueError("La replanification exige une absence confirmée")
    existing = await db.scalar(select(RendezVous).where(
        RendezVous.remplace_rdv_id == rdv.id,
        RendezVous.clinic_id == clinic_id,
        RendezVous.statut.notin_([StatutRDV.ANNULE.value, StatutRDV.NO_SHOW.value]),
    ))
    if existing:
        raise ValueError(f"Une replanification existe déjà (RDV #{existing.id})")
    new_start = _as_naive(datetime.fromisoformat(date_heure))
    duration = max(15, int((rdv.date_heure_fin - rdv.date_heure_debut).total_seconds() / 60)) if rdv.date_heure_fin else 30
    available = await get_disponibilites(rdv.praticien_id, new_start.date(), duration, db, clinic_id=clinic_id)
    available_values = {(_as_naive(datetime.fromisoformat(x.get("datetime", x) if isinstance(x, dict) else x))) for x in available}
    if new_start not in available_values:
        raise ValueError("Le créneau choisi n'est plus disponible")
    new_rdv, _ = await creer_rdv(
        patient_id=rdv.patient_id,
        praticien_id=rdv.praticien_id,
        acte_id=rdv.acte_id,
        date_heure=new_start,
        salle=rdv.salle,
        db=db,
        created_by=confirmed_by,
        clinic_id=clinic_id,
    )
    new_rdv.source = confirmation_source
    new_rdv.remplace_rdv_id = rdv.id
    new_rdv.reference = f"RDV-{new_rdv.id:06d}"
    await db.flush()
    await journaliser_evenement(
        db, rdv=new_rdv, type_evenement=EVENEMENT_CREATION,
        ancienne={}, nouvelle=snapshot_rdv(new_rdv), auteur_id=confirmed_by,
        motif=f"Replanification confirmée par le patient via {confirmation_source} — remplace RDV {rdv.id}",
    )
    task = TacheInterneAssistant(
        clinic_id=clinic_id,
        creee_par_id=confirmed_by,
        patient_id=rdv.patient_id,
        titre=f"Replanification confirmée — RDV #{new_rdv.id}",
        description=f"Le patient a confirmé le {new_start.strftime('%d/%m/%Y à %Hh%M')} via {confirmation_source}. RDV initial #{rdv.id} en no-show.",
        priorite="normale",
        statut=StatutTacheInterneEnum.A_FAIRE.value,
    )
    db.add(task)
    await db.commit()
    return {"old_rdv_id": rdv.id, "new_rdv_id": new_rdv.id, "patient_id": rdv.patient_id, "date_heure_debut": new_start.isoformat(), "statut": new_rdv.statut, "assistant_task_id": task.id, "whatsapp_status": "draft_only"}
