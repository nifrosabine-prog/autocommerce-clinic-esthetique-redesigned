from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api-server"
sys.path.insert(0, str(API))
load_dotenv(API / ".env.runtime.staging")

BRANDING = {
    "nom_clinique": "Clinique Esthétique",
    "logo_url": None,
    "couleur_primaire": "#0EA5A4",
    "couleur_secondaire": "#0F172A",
    "contenu_landing": {
        "titre": "Beauté naturelle, expertise médicale",
        "sous_titre": "Des soins esthétiques personnalisés dans un cadre sécurisé et confidentiel.",
        "services_mis_en_avant": ["Soin visage premium"],
        "adresse": "",
        "telephone": "",
        "horaires": "Sur rendez-vous",
    },
}

USERS = {
    1: ("Direction", "Clinique", "directrice@clinique-esthetique.tn"),
    2: ("Dr", "Médecin", "medecin@clinique-esthetique.tn"),
    3: ("Praticienne", "Esthétique", "estheticienne@clinique-esthetique.tn"),
    4: ("Assistante", "Accueil", "assistante@clinique-esthetique.tn"),
    5: ("Commercial", "Clinique", "commercial@clinique-esthetique.tn"),
    6: ("Administrateur", "Clinique", "admin@clinique-esthetique.tn"),
}


async def main(purge_demo: bool) -> None:
    if purge_demo and os.environ.get("ALLOW_PRODUCTION_RESET") != "true":
        raise SystemExit("Refus de purge : définir ALLOW_PRODUCTION_RESET=true explicitement.")
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        if purge_demo:
            await db.execute(text("""
                TRUNCATE TABLE
                  refresh_token_sessions, audit_logs_medicaux, audit_logs_financial,
                  booking_requests, dossiers_medicaux, consentements, factures,
                  fidelite_transactions, commissions, rendez_vous, patients, salles,
                  utilisateurs_actes
                RESTART IDENTITY CASCADE
            """))
            await db.execute(text("DELETE FROM utilisateurs WHERE email LIKE 'recette-%' OR email LIKE 'qa-%@example.test'"))
            await db.execute(text("DELETE FROM actes_medicaux WHERE clinic_id=1 AND id <> 1"))

        for user_id, (prenom, nom, email) in USERS.items():
            await db.execute(text("""
                UPDATE utilisateurs SET prenom=:prenom, nom=:nom, email=:email, is_active=true
                WHERE id=:user_id AND clinic_id=1
            """), {"prenom": prenom, "nom": nom, "email": email, "user_id": user_id})

        await db.execute(text("""
            UPDATE actes_medicaux
            SET nom='Soin visage premium', categorie='soin', duree_minutes=60,
                prix_base=180.000,
                description='Soin facial personnalisé dans un cadre médical sécurisé.',
                protocole='Accueil, analyse de peau, soin personnalisé et recommandations.',
                is_active=true
            WHERE id=1 AND clinic_id=1
        """))
        await db.execute(text("""
            INSERT INTO salles (clinic_id, nom, type, description, is_active, created_at)
            SELECT 1, 'Salle de soin esthétique', 'consultation',
                   'Salle principale dédiée aux soins esthétiques.', true, NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM salles
                WHERE clinic_id=1 AND nom='Salle de soin esthétique'
            )
        """))
        await db.execute(text("""
            INSERT INTO clinic_settings (clinic_id, key, value, description, updated_at)
            VALUES (1, 'branding', CAST(:value AS jsonb), 'Configuration de production initiale', NOW())
            ON CONFLICT (clinic_id, key) DO UPDATE
            SET value=EXCLUDED.value, description=EXCLUDED.description, updated_at=NOW()
        """), {"value": __import__("json").dumps(BRANDING, ensure_ascii=False)})
        await db.execute(text("""
            INSERT INTO clinic_settings (clinic_id, key, value, description, updated_at)
            VALUES (1, 'clinic.currency', CAST(:value AS jsonb), 'Devise de production', NOW())
            ON CONFLICT (clinic_id, key) DO UPDATE
            SET value=EXCLUDED.value, description=EXCLUDED.description, updated_at=NOW()
        """), {"value": '{"currency_code":"TND","currency_symbol":"DT"}'})
        await db.execute(text("""
            UPDATE clinic_subscriptions
            SET clinic_name='Clinique Esthétique', plan='premium', status='active', notes='Abonnement initial de production'
            WHERE clinic_id=1
        """))
        await db.commit()
    await engine.dispose()
    print("Production tenant prepared", "with demo purge" if purge_demo else "without demo purge")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--purge-demo", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.purge_demo))
