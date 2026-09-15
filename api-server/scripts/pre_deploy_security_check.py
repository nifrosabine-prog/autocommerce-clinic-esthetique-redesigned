#!/usr/bin/env python3
"""
AutoCommerce Clinic — Vérification pré-déploiement sécurité
Exécute les contrôles suivants :
  1. Aucun secret par défaut restant (SECRET_KEY, FERNET_KEY, DATABASE_URL, REDIS_URL)
  2. CORS != *
  3. ENV = production
  4. FERNET_KEY longueur >= 32 chars
  5. PHOTO_ENCRYPTION_KEY != DEFAULT
  6. Pas de print() dans les services métier (mauvaise pratique)
"""
import sys
import re
from pathlib import Path

# ── Chargement config ──────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import get_settings

DEFAULT_SECRET = "change-me-in-production-64-chars-minimum-for-jwt-signing"

errors = []
warnings = []


def check_secrets(settings):
    if settings.secret_key == DEFAULT_SECRET or len(settings.secret_key) < 64:
        errors.append("SECRET_KEY : valeur par défaut ou trop courte (< 64 chars)")
    if "changeme" in settings.database_url.lower():
        errors.append("DATABASE_URL : contient 'changeme' — mot de passe non modifié")
    if "changeme" in settings.redis_url.lower():
        errors.append("REDIS_URL : contient 'changeme' — mot de passe non modifié")
    if settings.cors_origins.strip() == "*":
        errors.append("CORS_ORIGINS : '*' est interdit en production")
    if settings.env != "production":
        errors.append(f"ENV : doit être 'production', actuellement '{settings.env}'")
    if len(settings.fernet_key) < 32:
        errors.append(f"FERNET_KEY : trop courte ({len(settings.fernet_key)} chars, min 32)")
    if settings.fernet_key and not _is_valid_fernet_key(settings.fernet_key):
        errors.append(
            "FERNET_KEY : format invalide — une clé Fernet doit faire exactement "
            "44 caractères (32 octets en base64 url-safe, padding '=' inclus), "
            "sans guillemets. Générer : python -c \"from cryptography.fernet "
            "import Fernet; print(Fernet.generate_key().decode())\""
        )
    if settings.mfa_encryption_key and not _is_valid_fernet_key(settings.mfa_encryption_key):
        errors.append("MFA_ENCRYPTION_KEY : format invalide — doit être une clé Fernet (44 caractères base64 url-safe)")
    if settings.photo_encryption_key == "default-photo-key-for-local-dev":
        errors.append("PHOTO_ENCRYPTION_KEY : valeur par défaut détectée")
    if not settings.fernet_key or len(settings.fernet_key) == 0:
        errors.append("FERNET_KEY : vide — chiffrement RGPD désactivé")


def _is_valid_fernet_key(value: str):
    """Même contrôle que config._is_valid_fernet_key (AUD-001) : refuse une
    clé présente mais mal formée AVANT le déploiement, pas au premier POST
    de dossier médical."""
    try:
        from cryptography.fernet import Fernet

        Fernet(value.encode())
        return True
    except Exception:
        return False


def check_deployment_policy(settings):
    """Vérifie les invariants réseau et egress du mode choisi."""
    if settings.deployment_mode == "internal_single_clinic":
        if not settings.clinic_id or settings.clinic_id <= 0:
            errors.append("DEPLOYMENT_MODE interne : CLINIC_ID positif requis")
        if settings.public_routes_enabled and settings.public_clinic_id != settings.clinic_id:
            errors.append("DEPLOYMENT_MODE interne : PUBLIC_CLINIC_ID doit être identique à CLINIC_ID")
        if settings.webhooks_enabled and settings.social_webhook_clinic_id != settings.clinic_id:
            errors.append("DEPLOYMENT_MODE interne : SOCIAL_WEBHOOK_CLINIC_ID doit être identique à CLINIC_ID")
        unauthorized = settings.allowed_external_integrations - {"ai", "whatsapp"}
        if unauthorized:
            errors.append(
                "DEPLOYMENT_MODE interne : intégrations externes interdites : "
                + ", ".join(sorted(unauthorized))
            )
        if any((settings.resend_api_key, settings.twilio_auth_token,
                settings.aws_access_key_id, settings.aws_secret_access_key,
                settings.smtp_host, settings.smtp_password)):
            errors.append("DEPLOYMENT_MODE interne : credentials Email/SMS/S3/SMTP interdits")

    if settings.whatsapp_enabled and not (settings.wa_business_token and settings.wa_phone_id):
        errors.append("WHATSAPP_ENABLED exige WA_BUSINESS_TOKEN et WA_PHONE_ID")
    if settings.llm_enabled and "ai" not in settings.allowed_external_integrations:
        errors.append("LLM_ENABLED exige que ai soit dans EXTERNAL_INTEGRATIONS_ALLOWLIST")
    if settings.llm_enabled and not settings.openai_api_key and settings.llm_provider == "openai":
        errors.append("LLM_PROVIDER=openai activé mais OPENAI_API_KEY absent")
    if settings.refresh_cookie_domain and any(marker in settings.refresh_cookie_domain.lower() for marker in ("localhost", ".local", "example")):
        errors.append("REFRESH_COOKIE_DOMAIN doit référencer le vrai domaine final ou rester vide")
    if settings.llm_max_tokens_per_request <= 0 or settings.llm_daily_token_budget <= 0:
        errors.append("Les plafonds IA doivent être strictement positifs")


def check_no_print_in_services():
    """Vérifie qu'aucun print() n'est présent dans les services métier."""
    services_dir = Path(__file__).resolve().parent.parent / "services"
    for py_file in services_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        content = py_file.read_text()
        # Chercher des print() non dans des commentaires
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.match(r'^\s*print\s*\(', stripped):
                warnings.append(f"{py_file.relative_to(services_dir.parent)}:{i}: print() détecté (utiliser logger)")


def check_dockerfile_no_env():
    """Vérifie que le Dockerfile ne copie PAS .env.clinic."""
    dockerfile = Path(__file__).resolve().parent.parent / "Dockerfile"
    if not dockerfile.exists():
        warnings.append("Dockerfile introuvable")
        return
    content = dockerfile.read_text()
    if ".env.clinic" in content:
        errors.append("Dockerfile : copie .env.clinic — secret exposé dans l'image !")


def check_production_nginx():
    """Vérifie que la config Nginx production est présente."""
    nginx_file = Path(__file__).resolve().parent.parent.parent / "nginx-production.conf"
    if not nginx_file.exists():
        warnings.append("nginx-production.conf manquant — pas de TLS configuré en production")


if __name__ == "__main__":
    print("=" * 60)
    print("AUTO-COMMERCE CLINIC — Vérification pré-déploiement")
    print("=" * 60)

    try:
        settings = get_settings()
        check_secrets(settings)
        check_deployment_policy(settings)
    except Exception as e:
        errors.append(f"Erreur chargement config : {e}")

    check_no_print_in_services()
    check_dockerfile_no_env()
    check_production_nginx()

    if errors:
        print(f"\n❌ BLOCAGES ({len(errors)} erreurs) :")
        for e in errors:
            print(f"  - {e}")

    if warnings:
        print(f"\n⚠️  ATTENTIONS ({len(warnings)} warnings) :")
        for w in warnings:
            print(f"  - {w}")

    if not errors and not warnings:
        print("\n✅ Tous les contrôles sont passés — déploiement autorisé")

    print("\n" + "=" * 60)
    sys.exit(1 if errors else 0)
