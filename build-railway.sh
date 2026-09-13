#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

npm install --global --force pnpm@10.15.1
pnpm install --frozen-lockfile
pnpm build:frontend

rm -rf api-server/web-dist
mkdir -p api-server/web-dist
cp -R autocommerce-app/dist/public/. api-server/web-dist/

test -s api-server/web-dist/index.html
echo "Frontend bundle prepared in api-server/web-dist"
