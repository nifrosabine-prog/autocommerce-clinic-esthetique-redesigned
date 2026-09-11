"""Allow human-validation workflow audit statuses.

Revision ID: 20260826_workflow_audit_status_length
Revises: 20260826_consentement_contrat_snapshot
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260826_workflow_audit_status_length"
down_revision: Union[str, None] = "20260826_consentement_contrat_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table fonctionne sur PostgreSQL comme sur SQLite ; ce
    # dernier ne supporte pas ALTER COLUMN TYPE en syntaxe native.
    with op.batch_alter_table("workflow_audit_logs") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=20),
            type_=sa.String(length=40),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Existing values longer than 20 characters must be normalized before
    # shrinking the column again; this keeps downgrade deterministic.
    op.execute(
        sa.text(
            "UPDATE workflow_audit_logs "
            "SET status = substr(status, 1, 20) "
            "WHERE length(status) > 20"
        )
    )
    with op.batch_alter_table("workflow_audit_logs") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(length=40),
            type_=sa.String(length=20),
            existing_nullable=False,
        )
