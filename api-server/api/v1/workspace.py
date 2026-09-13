"""Workspace clinique par rôle — prochaine action plutôt que statistiques."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from middleware.auth import get_current_active_user
from models.database import Patient, RendezVous
from models.episode_core import EpisodePatient, Intervention
from services.access_control import clinic_id_for

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _role(user: dict) -> str:
    return str(user.get("role", "")).replace("RoleEnum.", "").lower()


def _card(key: str, title: str, count: int, description: str, href: str, next_action: str, **context) -> dict:
    return {"key": key, "title": title, "count": int(count), "description": description,
            "href": href, "next_action": next_action, **context}


@router.get("")
async def get_workspace(
    current_user: dict = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    clinic_id = clinic_id_for(current_user)
    role = _role(current_user)
    now = datetime.utcnow()
    end = now + timedelta(days=1)
    cards: list[dict] = []

    if role == "assistante":
        expected = await db.scalar(select(func.count(RendezVous.id)).where(
            RendezVous.clinic_id == clinic_id,
            RendezVous.date_heure_debut >= now,
            RendezVous.date_heure_debut < end,
            RendezVous.statut.in_(["planifie", "confirme"]),
        ))
        arrived = await db.scalar(select(func.count(RendezVous.id)).where(
            RendezVous.clinic_id == clinic_id, RendezVous.statut == "arrive",
        ))
        cards = [
            _card("patients_attendus", "Patients attendus", expected or 0, "Rendez-vous du jour à préparer", "/accueil", "Ouvrir l’accueil des patients"),
            _card("patients_arrives", "Patients arrivés", arrived or 0, "Dossiers à compléter ou transmettre", "/accueil", "Ouvrir le dossier depuis l’accueil"),
        ]
    elif role in {"medecin", "estheticienne", "prestataire"}:
        assigned = await db.scalar(select(func.count(Intervention.id)).where(
            Intervention.clinic_id == clinic_id,
            Intervention.professionnel_id == int(current_user["id"]),
            Intervention.statut.in_(["planifiee", "en_cours"]),
        ))
        cards = [
            _card("interventions_affectees", "Interventions affectées", assigned or 0, "Interventions nécessitant votre action", "/clinical-ops", "Ouvrir les opérations cliniques"),
        ]
    else:
        open_episodes = await db.scalar(select(func.count(EpisodePatient.id)).where(
            EpisodePatient.clinic_id == clinic_id, EpisodePatient.statut == "ouvert",
        ))
        pending = await db.scalar(select(func.count(RendezVous.id)).where(
            RendezVous.clinic_id == clinic_id, RendezVous.statut.in_(["planifie", "confirme", "arrive"]),
        ))
        cards = [
            _card("episodes_ouverts", "Épisodes ouverts", open_episodes or 0, "Prises en charge à coordonner", "/clinical-ops", "Voir les opérations cliniques"),
            _card("rendez_vous_a_traiter", "Rendez-vous à traiter", pending or 0, "Agenda et accueil synchronisés", "/agenda", "Ouvrir l’agenda"),
        ]

    return {"role": role, "generated_at": now.isoformat(), "context": {"patient": None, "episode": None, "rdv": None}, "cards": cards}
