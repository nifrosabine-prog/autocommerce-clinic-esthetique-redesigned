"""P0-1 — Tests de l'instrumentation de la réactivation (timing + pool + script).

Ces tests ne nécessitent ni FastAPI ni base de données : ils couvrent le
seuil de lenteur du middleware de timing, la normalisation asyncpg de l'URL,
le durcissement du pool SQLAlchemy et la logique du script de recette.
"""

import os
import sys
from pathlib import Path
from unittest import mock

_API_SERVER = str(Path(__file__).resolve().parents[1])
if _API_SERVER not in sys.path:
    sys.path.insert(0, _API_SERVER)

from middleware.request_timing import SLOW_MS, is_slow
from models.database import get_async_engine, normalize_async_database_url
from scripts.activate_recipe_accounts import (
    DEFAULT_RECIPE_EMAILS,
    _sync_db_url,
    recipe_emails_from_env,
)


def test_is_slow_at_threshold():
    assert is_slow(SLOW_MS) is True
    assert is_slow(SLOW_MS - 1.0) is False


def test_normalize_url_forces_asyncpg():
    assert (
        normalize_async_database_url("postgresql://u:p@h:5432/db")
        == "postgresql+asyncpg://u:p@h:5432/db"
    )
    # Déjà asyncpg : inchangé.
    assert (
        normalize_async_database_url("postgresql+asyncpg://u:p@h/db")
        == "postgresql+asyncpg://u:p@h/db"
    )


def test_pool_hardening_applied_on_postgres_engine():
    engine = get_async_engine("postgresql://u:p@h:5432/db")
    pool = engine.pool
    assert pool._pre_ping is True
    assert pool._timeout == float(os.getenv("DB_POOL_TIMEOUT", "5"))
    assert pool._max_overflow == int(os.getenv("DB_MAX_OVERFLOW", "10"))
    # Taille effective de la file (interne SQLAlchemy) : selon la version,
    # maxsize vaut pool_size seul ou pool_size + max_overflow. Tolérant.
    qsize = getattr(getattr(pool, "_pool", None), "maxsize", None)
    pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
    overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    if qsize is not None:
        assert qsize in (pool_size, pool_size + overflow), f"maxsize={qsize} inattendu"


def test_sqlite_engine_still_creatable():
    # La création d'un moteur SQLite (tests / dev) ne doit pas échouer malgré
    # l'absence des paramètres de pool PostgreSQL.
    engine = get_async_engine("sqlite+aiosqlite:///./dev_pool_check.db")
    assert engine is not None


def test_recipe_emails_defaults_and_override():
    with mock.patch.dict(os.environ, {}, clear=False):
        emails = recipe_emails_from_env()
    assert emails == DEFAULT_RECIPE_EMAILS
    with mock.patch.dict(os.environ, {"ACTIVATE_RECIPE_EMAILS": "a@x.fr, b@x.fr"}, clear=False):
        assert recipe_emails_from_env() == ["a@x.fr", "b@x.fr"]


def test_sync_db_url_driver_swap():
    assert _sync_db_url("postgresql+asyncpg://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert _sync_db_url("postgresql://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert _sync_db_url("sqlite:///x.db") == "sqlite:///x.db"
