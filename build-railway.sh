#!/usr/bin/env bash
set -euo pipefail

ARCHIVE="clinic_esthetique_redesigned_ready_to_go (2).zip"
RELEASE_DIR="aesthetic_release_v3_final"
PREBUILT_FRONTEND="frontend-dist.tar.gz"

if [[ ! -d "$RELEASE_DIR" ]]; then
  unzip -q "$ARCHIVE"
fi

# Le frontend est compilé et testé avec PNPM dans l’environnement de validation,
# puis livré sous forme d’artefact statique. Railpack détecte Python à cause du
# backend FastAPI et ne fournit pas toujours Node/PNPM dans l’image de build.
# Cette étape évite Docker tout en déployant exactement le build PNPM validé.
mkdir -p "$RELEASE_DIR/autocommerce-app/dist"
tar -xzf "$PREBUILT_FRONTEND" -C "$RELEASE_DIR/autocommerce-app/dist"

# Garantir que FastAPI peut servir aussi le même build via main.py si nécessaire.
rm -rf "$RELEASE_DIR/api-server/web-dist"
cp -R "$RELEASE_DIR/autocommerce-app/dist/public" "$RELEASE_DIR/api-server/web-dist"
