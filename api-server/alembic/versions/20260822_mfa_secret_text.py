"""Allow encrypted TOTP secrets to exceed the legacy varchar(100) limit."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260822_mfa_secret_text"
down_revision: Union[str, None] = "20260822_pointage_open_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("utilisateurs") as batch_op:
        batch_op.alter_column(
            "mfa_secret",
            existing_type=sa.String(length=100),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    # Downgrade is intentionally explicit: existing encrypted values longer than
    # 100 characters would be truncated by PostgreSQL, so fail rather than lose
    # credentials silently.
    with op.batch_alter_table("utilisateurs") as batch_op:
        batch_op.alter_column(
            "mfa_secret",
            existing_type=sa.Text(),
            type_=sa.String(length=100),
            existing_nullable=True,
        )
