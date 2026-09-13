#!/usr/bin/env python
"""P0-1 — Activer un compte de recette par rôle (sans créer de doublon).

Usage :
    DATABASE_URL=postgresql://... python scripts/activate_recipe_accounts.py
    DATABASE_URL=... ACTIVATE_RECIPE_EMAILS=a@x.fr,b@x.fr python scripts/activate_recipe_accounts.py
    ACTIVATE_RECIPE_PASSWORD='MotDePasse!2026'  # optionnel : réinitialise aussi le mot de passe

Le script ne fait qu'activer des comptes EXISTANTS (UPDATE is_active=true) :
aucune création, donc aucun risque de doublon d'e-mail. Les comptes absents
sont signalés pour être créés depuis l'interface Gestion Équipe (création
déjà auditée dans audit_logs_team).
"""

import os
import sys

from sqlalchemy import create_engine, text

# Comptes de recette attendus par rôle (surchargés par ACTIVATE_RECIPE_EMAILS).
DEFAULT_RECIPE_EMAILS = [
    "medecin.recette@clinic.local",
    "assistante.recette@clinic.local",
    "commercial.recette@clinic.local",
    "estheticienne.recette@clinic.local",
]


def recipe_emails_from_env() -> list:
    raw = os.getenv("ACTIVATE_RECIPE_EMAILS", "").strip()
    if not raw:
        return list(DEFAULT_RECIPE_EMAILS)
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _sync_db_url(database_url: str) -> str:
    """Remplace le driver async par psycopg2 pour les scripts synchrones."""
    url = (database_url or "").strip().strip('"\'')
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Erreur : DATABASE_URL doit être défini.")
        return 1

    clinic_id = int(os.getenv("CLINIC_ID", "1"))
    emails = recipe_emails_from_env()
    password = os.getenv("ACTIVATE_RECIPE_PASSWORD", "").strip() or None

    pwd_context = None
    if password:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    engine = create_engine(_sync_db_url(database_url))

    activated, missing = [], []
    try:
        with engine.connect() as conn:
            for email in emails:
                params = {"email": email, "clinic_id": clinic_id}
                sql = "UPDATE utilisateurs SET is_active = true, updated_at = NOW()"
                if password:
                    params["hashed_password"] = pwd_context.hash(password)
                    sql += ", hashed_password = :hashed_password"
                sql += " WHERE email = :email AND clinic_id = :clinic_id"
                result = conn.execute(text(sql), params)
                if result.rowcount > 0:
                    activated.append(email)
                    print(f"✓ Activé : {email}")
                else:
                    missing.append(email)
                    print(f"✗ Introuvable : {email} (à créer depuis Gestion Équipe)")
            conn.commit()
    except Exception as exc:
        print(f"Erreur : {exc}")
        return 1

    print(f"\nRésumé : {len(activated)} activé(s), {len(missing)} manquant(s).")
    for email in missing:
        print(f"  - {email}")
    if missing:
        print("Comptes manquants à créer via l'interface (création auditable).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
