"""Correctif AUD-003 (2026-09-11) — restaure les dix actes de recette.

L'audit VPS du 11/09/2026 n'a trouvé qu'un seul acte (« Acte VPS interne »)
au lieu des dix attendus, ce qui a rendu impossible la vérification de la
matrice d'attribution praticien/acte et des workflows associés.

Ce script est idempotent : il crée chaque acte S'IL N'EXISTE PAS déjà dans
la clinique (unicité garantie par la contrainte uq_actes_clinic_nom_normalise
via la normalisation de nom), ne modifie jamais un acte existant, et peut
donc être relancé sans risque sur le VPS de recette.

Usage (sur le VPS, conteneur api) :
    python scripts/seed_actes_recette.py

Optionnel — rattacher les praticiens (ids séparés par des virgules) :
    PRATICIEN_IDS="3,4" python scripts/seed_actes_recette.py

La variable CLINIC_ID (défaut 1) est lue depuis l'environnement.
"""
from __future__ import annotations

import asyncio
import os
from decimal import Decimal

from sqlalchemy import select

from config import get_settings
from models.database import ActeMedical, Utilisateur

# Les dix actes de recette attendus par l'audit (AUD-003).
# prix en DT (dinars), durée en minutes ; public = réservable depuis la landing.
ACTES_RECETTE: list[dict] = [
    {"nom": "Consultation esthétique", "categorie": "consultation", "duree_minutes": 30, "prix": "80.000", "public": True},
    {"nom": "Injection acide hyaluronique lèvres", "categorie": "injectable", "duree_minutes": 45, "prix": "600.000", "public": True},
    {"nom": "Injection acide hyaluronique jouges", "categorie": "injectable", "duree_minutes": 45, "prix": "700.000", "public": True},
    {"nom": "Botox front", "categorie": "injectable", "duree_minutes": 30, "prix": "450.000", "public": True},
    {"nom": "Botox ride du lion", "categorie": "injectable", "duree_minutes": 30, "prix": "400.000", "public": True},
    {"nom": "Peeling superficiel", "categorie": "soin", "duree_minutes": 30, "prix": "120.000", "public": True},
    {"nom": "Microneedling", "categorie": "soin", "duree_minutes": 45, "prix": "180.000", "public": True},
    {"nom": "Nettoyage de peau profond", "categorie": "soin", "duree_minutes": 60, "prix": "90.000", "public": True},
    {"nom": "Épilation laser maillot", "categorie": "laser", "duree_minutes": 30, "prix": "150.000", "public": True},
    {"nom": "Séance mésothérapie visage", "categorie": "injectable", "duree_minutes": 45, "prix": "250.000", "public": False},
]


def _praticien_ids_from_env() -> list[int]:
    raw = (os.getenv("PRATICIEN_IDS") or "").strip()
    ids: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.append(int(chunk))
    return ids


async def seed_actes() -> None:
    settings = get_settings()
    clinic_id = int(os.getenv("CLINIC_ID") or settings.clinic_id or 1)

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    created: list[str] = []
    skipped: list[str] = []

    async with Session() as db:
        praticiens: list[Utilisateur] = []
        ids = _praticien_ids_from_env()
        if ids:
            result = await db.execute(
                select(Utilisateur).where(
                    Utilisateur.id.in_(ids), Utilisateur.clinic_id == clinic_id
                )
            )
            praticiens = list(result.scalars().all())

        for spec in ACTES_RECETTE:
            existant = (
                await db.execute(
                    select(ActeMedical).where(
                        ActeMedical.clinic_id == clinic_id,
                        ActeMedical.nom == spec["nom"],
                    )
                )
            ).scalar_one_or_none()
            if existant is not None:
                skipped.append(spec["nom"])
                continue

            acte = ActeMedical(
                clinic_id=clinic_id,
                nom=spec["nom"],
                categorie=spec["categorie"],
                duree_minutes=spec["duree_minutes"],
                prix_base=Decimal(spec["prix"]),
                description=f"Acte de recette — {spec['nom']}.",
                is_active=True,
                is_public=spec["public"],
            )
            if praticiens:
                acte.praticiens = list(praticiens)
            db.add(acte)
            created.append(spec["nom"])

        await db.commit()

    print(f"AUD-003 seed actes : {len(created)} créé(s), {len(skipped)} déjà présent(s).")
    for nom in created:
        print(f"  + {nom}")
    if praticiens:
        print(f"Praticiens rattachés : {', '.join(f'#{u.id} {u.prenom} {u.nom}' for u in praticiens)}")
    if settings.env == "production":
        print(
            "ATTENTION : ENV=production — ce script est prévu pour la recette ; "
            "vérifier que l'opération est souhaitée sur cet environnement."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_actes())
