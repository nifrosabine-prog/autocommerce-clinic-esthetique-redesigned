"""Assainissement ciblé des données synthétiques identifiées par marqueurs connus.

Par défaut le script est en lecture seule. Avec --apply et
ALLOW_SYNTHETIC_CLEANUP=1, il masque les actes de recette connus du catalogue
public et désactive les comptes de démonstration. Il ne supprime aucune ligne,
ne déduit jamais une donnée de test d’après un nom générique et refuse la
production sans un environnement explicitement déclaré de staging/QA.
"""
from __future__ import annotations

import argparse
import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import get_settings
from models.database import ActeMedical, Utilisateur


SYNTHETIC_EMAIL_SUFFIXES = ("@clinic.local", ".demo@clinique-esthetique.local")
SYNTHETIC_ACTE_MARKERS = (" - recette", "qa synthétique")


async def main(apply: bool) -> None:
    settings = get_settings()
    if settings.env == "production":
        raise RuntimeError("Ce script refuse toute exécution en production.")
    if apply and os.getenv("ALLOW_SYNTHETIC_CLEANUP") != "1":
        raise RuntimeError("L’application exige ALLOW_SYNTHETIC_CLEANUP=1.")

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        users = (await db.execute(select(Utilisateur))).scalars().all()
        actes = (await db.execute(select(ActeMedical))).scalars().all()
        marked_users = [user for user in users if user.email.lower().endswith(SYNTHETIC_EMAIL_SUFFIXES)]
        marked_actes = [acte for acte in actes if any(marker in acte.nom.casefold() for marker in SYNTHETIC_ACTE_MARKERS)]

        print(f"UTILISATEURS_SYNTHETIQUES={len(marked_users)}")
        print(f"ACTES_SYNTHETIQUES={len(marked_actes)}")
        for user in marked_users:
            print(f"USER id={user.id} email={user.email}")
        for acte in marked_actes:
            print(f"ACTE id={acte.id} nom={acte.nom}")

        if apply:
            for user in marked_users:
                user.is_active = False
                user.is_public = False
            for acte in marked_actes:
                acte.is_active = False
                acte.is_public = False
            await db.commit()
            print("ASSAINISSEMENT_APPLIQUE=1")
        else:
            print("MODE_DRY_RUN=1")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Applique l’assainissement après revue du dry run.")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
