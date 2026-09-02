#!/usr/bin/env bash

set -euo pipefail



ARCHIVE="AutoCommerce-Clinic-RBAC-Workflow-Corrige-GitHub.zip"

RELEASE_DIR="aesthetic_release_latest"

rm -rf "$RELEASE_DIR"

mkdir -p "$RELEASE_DIR"



unzip -q -o "$ARCHIVE" -d "$RELEASE_DIR/.extracted"

shopt -s dotglob

ROOT_DIR="$RELEASE_DIR/.extracted"

if [ -d "$ROOT_DIR/autocommerce-clinic-github-final" ]; then

  ROOT_DIR="$ROOT_DIR/autocommerce-clinic-github-final"
  
fi

cp -a "$ROOT_DIR"/. "$RELEASE_DIR"/

rm -rf "$RELEASE_DIR/.extracted"



if [ ! -d "$RELEASE_DIR/api-server" ] || [ ! -d "$RELEASE_DIR/autocommerce-app" ]; then

  echo "Archive layout invalid: expected api-server/ and autocommerce-app/" >&2
  
  exit 1
  
fi



cd "$RELEASE_DIR/autocommerce-app"

corepack enable

pnpm install --frozen-lockfile

pnpm build



rm -rf "../api-server/web-dist"

mkdir -p "../api-server/web-dist"

cp -R dist/public/. "../api-server/web-dist/"



echo "Prepared release directory: $RELEASE_DIR"

echo "Frontend bundle: $RELEASE_DIR/api-server/web-dist"




