#!/usr/bin/env bash
set -euo pipefail
ARCHIVE="clinic_esthetique_redesigned_ready_to_go (2).zip"
RELEASE_DIR="aesthetic_release_v3_final"
if [[ ! -d "$RELEASE_DIR" ]]; then
  unzip -q "$ARCHIVE"
fi
cd "$RELEASE_DIR"
pnpm install --frozen-lockfile
pnpm build:frontend
