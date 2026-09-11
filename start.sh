#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "Démarrage de AutoCommerce Clinic..."

ENV_FILE="${DEPLOY_ENV_FILE:-.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "[NO-GO] Fichier d’environnement absent : $ENV_FILE" >&2
  echo "        Préparez un fichier externe à partir de .env.example ou exportez DEPLOY_ENV_FILE." >&2
  exit 2
fi

if [[ ! -f "autocommerce-app/dist/public/index.html" ]]; then
  echo "[NO-GO] Le frontend n’est pas buildé." >&2
  echo "        Exécutez : pnpm install --frozen-lockfile && pnpm build:frontend" >&2
  exit 2
fi

# Charge uniquement le fichier de secrets préparé localement dans l’environnement
# du processus ; aucun secret n’est copié dans l’image ou dans le dépôt.
set -a
. "$ENV_FILE"
set +a

cd api-server
exec python3 run_combined.py
