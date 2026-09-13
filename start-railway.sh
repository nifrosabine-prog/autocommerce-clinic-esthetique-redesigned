#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR/api-server"

if [[ "${SEED_ACTES_RECETTE:-false}" == "true" ]]; then
  echo "Seeding recipe acts..."
  python scripts/seed_actes_recette.py
fi

if [[ -n "${BOOTSTRAP_ADMIN_EMAIL:-}" || -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  echo "Bootstrapping initial administrator..."
  python bootstrap_admin.py --from-env
fi

echo "Starting AutoCommerce Clinic on port ${PORT:-8000}..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
