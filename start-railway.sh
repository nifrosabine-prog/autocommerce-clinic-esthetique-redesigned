#!/usr/bin/env bash
set -euo pipefail

cd aesthetic_release_v3_final/api-server

alembic upgrade head

if [[ -n "${BOOTSTRAP_ADMIN_EMAIL:-}" || -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  python bootstrap_admin.py --from-env
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
