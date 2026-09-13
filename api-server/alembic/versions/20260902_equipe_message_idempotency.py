"""Add idempotency keys to team messages.

Revision ID: 20260902_equipe_message_idempotency
Revises: 20260831_recrutement_history
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260902_equipe_message_idempotency"
down_revision: Union[str, None] = "20260831_recrutement_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("equipe_messages", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_equipe_messages_send_idempotency",
        "equipe_messages",
        ["clinic_id", "expediteur_id", "idempotency_key", "destinataire_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_equipe_messages_send_idempotency", table_name="equipe_messages")
    op.drop_column("equipe_messages", "idempotency_key")
