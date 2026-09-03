#!/usr/bin/env bash

set -euo pipefail

ARCHIVE="AutoCommerce-Clinic-RBAC-Workflow-Corrige-GitHub-fixed-v2.zip"

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

# The Railway Python image may not provide Node.js/corepack. Install a local Node runtime

# and PNPM so the frontend build is reproducible and does not depend on the base image.

if ! command -v node >/dev/null 2>&1; then

  NODE_VERSION=22.14.0
  
  NODE_DIR="$HOME/.railway-node-v$NODE_VERSION"
  
  if [ ! -x "$NODE_DIR/bin/node" ]; then
  
    mkdir -p "$HOME/.railway-node"
    
    curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.xz" -o "$HOME/.railway-node/node.tar.xz"
    
    rm -rf "$NODE_DIR"
    
    mkdir -p "$NODE_DIR"
    
    tar -xJf "$HOME/.railway-node/node.tar.xz" --strip-components=1 -C "$NODE_DIR"
    
    rm -f "$HOME/.railway-node/node.tar.xz"
    
  fi
  
  export PATH="$NODE_DIR/bin:$PATH"
  
fi

if ! command -v pnpm >/dev/null 2>&1; then

  npm install --global pnpm@9.15.0
  
fi

cd "$RELEASE_DIR/autocommerce-app"

pnpm install --frozen-lockfile

pnpm build

rm -rf "../api-server/web-dist"

mkdir -p "../api-server/web-dist"

cp -R dist/public/. "../api-server/web-dist/"

echo "Prepared release directory: $RELEASE_DIR"

echo "Frontend bundle: $RELEASE_DIR/api-server/web-dist"














