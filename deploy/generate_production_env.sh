#!/usr/bin/env bash
# Génère deploy/production.env à partir de deploy/production.env.example
# avec de vraies clés aléatoires (jamais de secret en dur dans le dépôt).
#
# Usage sur le VPS (jamais en local, jamais commité) :
#   cd deploy && ./generate_production_env.sh
#
# Corrige le point bloquant n°2 du rapport d'audit (2026-09-06) :
# le .env.example est volontairement à placeholders ; ce script produit
# la version réelle sans jamais qu'un humain tape/lise une clé faible.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE="$HERE/production.env.example"
TARGET="$HERE/production.env"

if [ -f "$TARGET" ]; then
  echo "⚠️  $TARGET existe déjà. Suppression manuelle requise avant régénération (pour éviter d'écraser des secrets en usage)." >&2
  exit 1
fi

command -v openssl >/dev/null 2>&1 || { echo "openssl est requis." >&2; exit 1; }

read -rp "Domaine public (ex. clinic.exemple.tld) : " DOMAIN
if [ -z "$DOMAIN" ]; then
  echo "Domaine obligatoire (utilisé par Caddy pour le certificat TLS)." >&2
  exit 1
fi

POSTGRES_PASSWORD="$(openssl rand -base64 32 | tr -d '\n')"
SECRET_KEY="$(openssl rand -base64 64 | tr -d '\n')"
# Correctif AUD-001 (2026-09-11) : ne PAS rajouter de « = » manuel.
# `openssl rand -base64 32` produit déjà 44 caractères avec le padding « = » :
# l'ancienne ligne (…| tr -d '\n')=" produisait une clé de 45 caractères et
# toute clé mal formée casse le dossier médical (erreur Fernet au premier POST).
FERNET_KEY="$(openssl rand -base64 32 | tr -- '+/' '-_' | tr -d '\n')"
PHOTO_ENCRYPTION_KEY="$(openssl rand -base64 32 | tr -- '+/' '-_' | tr -d '\n')"
MFA_ENCRYPTION_KEY="$(openssl rand -base64 32 | tr -- '+/' '-_' | tr -d '\n')"

sed \
  -e "s#^DOMAIN=.*#DOMAIN=${DOMAIN}#" \
  -e "s#^CORS_ORIGINS=.*#CORS_ORIGINS=https://${DOMAIN}#" \
  -e "s#^POSTGRES_PASSWORD=.*#POSTGRES_PASSWORD=${POSTGRES_PASSWORD}#" \
  -e "s#^SECRET_KEY=.*#SECRET_KEY=${SECRET_KEY}#" \
  -e "s#^FERNET_KEY=.*#FERNET_KEY=${FERNET_KEY}#" \
  -e "s#^PHOTO_ENCRYPTION_KEY=.*#PHOTO_ENCRYPTION_KEY=${PHOTO_ENCRYPTION_KEY}#" \
  -e "s#^MFA_ENCRYPTION_KEY=.*#MFA_ENCRYPTION_KEY=${MFA_ENCRYPTION_KEY}#" \
  "$EXAMPLE" > "$TARGET"

chmod 600 "$TARGET"

echo "✅ $TARGET créé (chmod 600)."
echo "Reste à faire manuellement :"
echo "  - Vérifier/adapter POSTGRES_DB, POSTGRES_USER, WEB_PORT si besoin."
echo "  - Si compte directrice initial nécessaire : décommenter et remplir"
echo "    BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD, PUIS les retirer"
echo "    du fichier une fois le compte créé (voir api-server/start.sh)."
echo "  - Ne jamais committer ni relivrer ce fichier dans une archive."
