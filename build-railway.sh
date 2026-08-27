#!/usr/bin/env bash
set -euo pipefail
ARCHIVE="clinic_esthetique_redesigned_audit_global.zip"
RELEASE_DIR="aesthetic_release_v3_final"
PREBUILT_FRONTEND="frontend-dist.tar.gz"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
unzip -q -o "$ARCHIVE" -d "$RELEASE_DIR"
if [ -d "$RELEASE_DIR/app" ]; then
  shopt -s dotglob
  mv "$RELEASE_DIR/app"/* "$RELEASE_DIR/"
  rmdir "$RELEASE_DIR/app"
  shopt -u dotglob
fi
mkdir -p "$RELEASE_DIR/autocommerce-app/dist"
tar -xzf "$PREBUILT_FRONTEND" -C "$RELEASE_DIR/autocommerce-app/dist"
rm -rf "$RELEASE_DIR/api-server/web-dist"
cp -R "$RELEASE_DIR/autocommerce-app/dist/public" "$RELEASE_DIR/api-server/web-dist"
echo "Prepared release directory: $RELEASE_DIR"
echo "Frontend bundle: $RELEASE_DIR/autocommerce-app/dist/public"
