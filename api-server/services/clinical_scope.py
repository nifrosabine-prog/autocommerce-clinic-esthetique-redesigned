"""Validation centralisée des rattachements cliniques du Bloc 1."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.episode_core import EpisodePatient, Intervention


async def validate_episode_intervention_scope(
    db: AsyncSession,
    *,
    patient_id: int,
    clinic_id: int,
    episode_id: Optional[int] = None,
    intervention_id: Optional[int] = None,
) -> tuple[Optional[EpisodePatient], Optional[Intervention]]:
    """Valide une portée clinique cohérente avant toute création métier.

    Les deux identifiants restent optionnels pour préserver les données et
    intégrations historiques. Dès qu'un rattachement est fourni, toutes les
    relations patient/clinique/épisode/intervention sont vérifiées côté API.
    """
    episode = None
    intervention = None
    if intervention_id is not None and episode_id is None:
        raise ValueError("intervention_id requiert episode_id")

    if episode_id is not None:
        episode = await db.scalar(
            select(EpisodePatient).where(
                EpisodePatient.id == episode_id,
                EpisodePatient.patient_id == patient_id,
                EpisodePatient.clinic_id == clinic_id,
            )
        )
        if episode is None:
            raise ValueError("Épisode introuvable pour ce patient et cette clinique")

    if intervention_id is not None:
        intervention = await db.scalar(
            select(Intervention).where(
                Intervention.id == intervention_id,
                Intervention.episode_id == episode_id,
                Intervention.clinic_id == clinic_id,
            )
        )
        if intervention is None:
            raise ValueError("Intervention introuvable dans cet épisode et cette clinique")

    return episode, intervention
