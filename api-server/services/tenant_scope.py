"""Résolution centralisée du contexte clinique serveur."""
from __future__ import annotations

from typing import Optional

from config import get_settings


def resolve_clinic_id(clinic_id: Optional[int]) -> int:
    """Retourne un tenant positif ou refuse en production.

    Les valeurs implicites sont tolérées uniquement en test/développement et
    pour le mode mono-clinique explicitement configuré. Le mode enterprise ne
    doit jamais retomber sur la clinique 1.
    """
    if clinic_id is not None and int(clinic_id) > 0:
        return int(clinic_id)
    settings = get_settings()
    if settings.env in {"test", "development"}:
        return int(settings.clinic_id or 1)
    if settings.is_internal_single_clinic and settings.clinic_id:
        return int(settings.clinic_id)
    raise ValueError("Contexte clinique obligatoire")
