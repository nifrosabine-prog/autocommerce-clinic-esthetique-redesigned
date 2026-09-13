#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "Running database migrations..."
alembic upgrade head

# Correctif AUD-003 (2026-09-11) : restauration idempotente des dix actes
# de recette (l'audit VPS n'en trouvait qu'un). Sans effet si les actes
# existent déjà ; ne s'exécute que si SEED_ACTES_RECETTE=true.
if [[ "${SEED_ACTES_RECETTE:-}" == "true" ]]; then
  echo "Seeding des 10 actes de recette (AUD-003)..."
  python scripts/seed_actes_recette.py
fi

# Seed optionnel et idempotent du compte initial. Le mot de passe est lu
# uniquement depuis les variables Railway BOOTSTRAP_ADMIN_*.
if [[ -n "${BOOTSTRAP_ADMIN_EMAIL:-}" || -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  echo "Seeding initial admin account..."
  python bootstrap_admin.py --from-env
fi

echo "Starting Uvicorn server..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
