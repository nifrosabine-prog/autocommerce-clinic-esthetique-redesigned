"""Tests — config.py (_validate_production_secrets)

Vérifie le garde-fou qui empêche de démarrer en production avec des
secrets par défaut ou absents.
"""
import pytest
from cryptography.fernet import Fernet

from config import Settings, _validate_production_secrets, DEFAULT_SECRET_KEY


def _settings(**overrides):
    base = dict(
        env="production",
        clinic_id=1,
        public_clinic_id=1,
        secret_key="S" * 64,
        # Correctif AUD-001 : clés Fernet réelles (44 caractères base64
        # url-safe) — la validation refuse désormais tout autre format.
        fernet_key=Fernet.generate_key().decode(),
        photo_encryption_key=Fernet.generate_key().decode(),
        mfa_encryption_key=Fernet.generate_key().decode(),
        database_url="postgresql+asyncpg://real_user:real_pass@db.clinic.tn:5432/clinic",
        redis_url="redis://:real_redis_key@redis.clinic.tn:6379/0",
        social_webhook_clinic_id=1,
        cors_origins="https://app.clinic.tn",
        wa_allow_dev_mode=False,
    )
    base.update(overrides)
    return Settings(**base)


def test_valid_production_config_passes():
    _validate_production_secrets(_settings())  # ne doit pas lever


def test_default_secret_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _validate_production_secrets(_settings(secret_key=DEFAULT_SECRET_KEY))


def test_short_secret_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _validate_production_secrets(_settings(secret_key="trop-court"))


def test_missing_fernet_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        _validate_production_secrets(_settings(fernet_key=""))


def test_missing_photo_encryption_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="PHOTO_ENCRYPTION_KEY"):
        _validate_production_secrets(_settings(photo_encryption_key=""))


def test_photo_encryption_key_same_as_fernet_key_rejected():
    same_key = Fernet.generate_key().decode()
    with pytest.raises(RuntimeError, match="PHOTO_ENCRYPTION_KEY"):
        _validate_production_secrets(_settings(
            fernet_key=same_key, photo_encryption_key=same_key,
        ))


def test_default_database_credentials_rejected_in_production():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        _validate_production_secrets(_settings(
            database_url="postgresql+asyncpg://clinic_admin:changeme@localhost:5432/autocommerce_clinic"
        ))


def test_development_env_skips_validation():
    """En dev/test, on ne bloque jamais — sinon on casse le développement local."""
    _validate_production_secrets(_settings(env="development", secret_key=DEFAULT_SECRET_KEY, fernet_key=""))


def test_all_errors_reported_together():
    with pytest.raises(RuntimeError) as exc:
        _validate_production_secrets(_settings(secret_key=DEFAULT_SECRET_KEY, fernet_key=""))
    assert "SECRET_KEY" in str(exc.value)
    assert "FERNET_KEY" in str(exc.value)


def test_placeholder_redis_credentials_rejected_in_production():
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        _validate_production_secrets(_settings(
            redis_url="redis://:password@example-redis:6379/0"
        ))


def test_placeholder_critical_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _validate_production_secrets(_settings(
            secret_key="your-secret-key-please-change-1234567890"
        ))


def test_whatsapp_dev_mode_rejected_in_production():
    with pytest.raises(RuntimeError, match="WA_ALLOW_DEV_MODE"):
        _validate_production_secrets(_settings(wa_allow_dev_mode=True))


# ── Correctif AUD-001 : format des clés Fernet ──────────────────────

def test_malformed_fernet_key_rejected_in_production():
    """Une clé présente mais mal formée doit être refusée au démarrage,
    pas découverte au premier POST de dossier médical (AUD-001)."""
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        _validate_production_secrets(_settings(fernet_key="pas-une-cle-fernet-valide"))


def test_placeholder_fernet_key_rejected_in_production():
    """Scénario exact de l'audit du 2026-09-11 : le placeholder de
    production.env.example n'a pas été remplacé (43 caractères, non
    décodable en 32 octets) → refus au démarrage."""
    with pytest.raises(RuntimeError, match="FERNET_KEY"):
        _validate_production_secrets(
            _settings(fernet_key="REMPLACER_PAR_UNE_CLE_FERNET_BASE64_URLSAFE")
        )


def test_valid_generated_fernet_key_passes():
    _validate_production_secrets(
        _settings(
            fernet_key=Fernet.generate_key().decode(),
            photo_encryption_key=Fernet.generate_key().decode(),
            mfa_encryption_key=Fernet.generate_key().decode(),
        )
    )  # ne doit pas lever


def test_malformed_mfa_encryption_key_rejected_in_production():
    with pytest.raises(RuntimeError, match="MFA_ENCRYPTION_KEY"):
        _validate_production_secrets(_settings(mfa_encryption_key="toto"))


def test_identical_valid_fernet_keys_still_rejected():
    """La règle d'unicité des clés s'applique aussi à des clés valides."""
    same_key = Fernet.generate_key().decode()
    with pytest.raises(RuntimeError, match="PHOTO_ENCRYPTION_KEY"):
        _validate_production_secrets(
            _settings(fernet_key=same_key, photo_encryption_key=same_key)
        )
