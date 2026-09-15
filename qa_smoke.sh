#!/usr/bin/env bash
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8080}"
login() {
  local role="$1" email="$2" password="$3"
  local body status token
  body=$(curl -sS -w '\n%{http_code}' -X POST "$BASE/api/v1/auth/login" -H 'Content-Type: application/json' -d "{\"identifier\":\"$email\",\"password\":\"$password\"}")
  status=$(tail -n1 <<< "$body"); token=$(head -n-1 <<< "$body" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
  test "$status" = 200
  test -n "$token"
  me=$(curl -sS -w '\n%{http_code}' "$BASE/api/v1/auth/me" -H "Authorization: Bearer $token")
  test "$(tail -n1 <<< "$me")" = 200
  echo "$role login OK: $(head -n-1 <<< "$me")"
}
test "$(curl -sS "$BASE/api/health")" = '{"status":"ok"}'
login admin admin.qa@autoclinique.test 'AdminQA-2026-Secure!'
login medecin medecin.qa@autoclinique.test 'MedecinQA-2026-Secure!'
login estheticienne estheticienne.qa@autoclinique.test 'RoleQA-2026-Secure!'
login assistante assistante.qa@autoclinique.test 'RoleQA-2026-Secure!'
landing=$(curl -sS "$BASE/")
grep -q '<!doctype html>' <<< "$landing"
echo "frontend public OK"
