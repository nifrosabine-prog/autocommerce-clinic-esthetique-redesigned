"""Bloc 5 — idempotence des messages entrants webhook.

Revision ID: block5_webhook_idempotency
Revises: block3_refresh_tokens
"""
from alembic import op

revision = "block5_webhook_idempotency"
down_revision = "block3_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("messages_omnicanal") as batch_op:
        batch_op.create_unique_constraint(
            "uq_messages_conversation_external_id",
            ["conversation_id", "external_message_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("messages_omnicanal") as batch_op:
        batch_op.drop_constraint("uq_messages_conversation_external_id", type_="unique")
