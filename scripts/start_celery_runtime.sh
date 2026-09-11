#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT/api-server"
ENV_FILE="${ENV_FILE:-$API_DIR/.env.runtime.staging}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
export PYTHONPATH="$API_DIR${PYTHONPATH:+:$PYTHONPATH}"
cd "$API_DIR"

case "${1:-worker}" in
  worker)
    exec celery -A services.celery_app.celery worker --loglevel="${CELERY_LOGLEVEL:-INFO}" --concurrency="${CELERY_CONCURRENCY:-1}"
    ;;
  beat)
    exec celery -A services.celery_app.celery beat --loglevel="${CELERY_LOGLEVEL:-INFO}"
    ;;
  *)
    echo "Usage: $0 worker|beat" >&2
    exit 2
    ;;
esac
