#!/usr/bin/env bash
set -euo pipefail
ARCHIVE="clinic_esthetique_redesigned_ready_to_go (2).zip"
RELEASE_DIR="aesthetic_release_v3_final"
if [[ ! -d "$RELEASE_DIR" ]]; then
  unzip -q "$ARCHIVE"
fi
cd "$RELEASE_DIR"
# Railpack peut sélectionner le runtime Python lorsque requirements.txt est présent.
# Installer PNPM explicitement afin de conserver le build frontend sans Docker.
if ! command -v pnpm >/dev/null 2>&1; then
  corepack enable 2>/dev/null || true
  corepack prepare pnpm@10.15.1 --activate 2>/dev/null || npm install --global pnpm@10.15.1
fi
pnpm install --frozen-lockfile
pnpm build:frontend
