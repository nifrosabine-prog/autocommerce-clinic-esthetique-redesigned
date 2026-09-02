#!/usr/bin/env bash

set -euo pipefail



cd aesthetic_release_latest/api-server

alembic upgrade head

if [[ -n "${BOOTSTRAP_ADMIN_EMAIL:-}" || -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then

  python bootstrap_admin.py --from-env
  
fi

exec python run_combined.py


