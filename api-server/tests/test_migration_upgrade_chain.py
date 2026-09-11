from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


API_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_RELEASE_HEAD = "20260822_mfa_secret_text"
CURRENT_HEAD = "20260826_workflow_audit_status_length"


def run_alembic(arguments: list[str], environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=API_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def test_upgrade_from_previously_deployed_schema_to_current_head(tmp_path: Path) -> None:
    """Le schéma de la release précédente doit pouvoir évoluer sans arrêter Railway."""
    environment = os.environ.copy()
    environment.update(
        {
            "ENV": "test",
            "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'upgrade_chain.db'}",
            "REDIS_URL": "redis://127.0.0.1:6379/14",
        }
    )

    previous_upgrade = run_alembic(["upgrade", PREVIOUS_RELEASE_HEAD], environment)
    assert previous_upgrade.returncode == 0, previous_upgrade.stderr

    current_upgrade = run_alembic(["upgrade", "head"], environment)
    assert current_upgrade.returncode == 0, current_upgrade.stderr

    current_revision = run_alembic(["current"], environment)
    assert current_revision.returncode == 0, current_revision.stderr
    assert CURRENT_HEAD in current_revision.stdout
