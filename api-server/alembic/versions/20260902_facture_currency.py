"""Persist invoice currency metadata.

Revision ID: 20260902_facture_currency
Revises: 20260902_equipe_message_idempotency
"""
from alembic import op
import sqlalchemy as sa

revision = "20260902_facture_currency"
down_revision = "20260902_equipe_message_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("factures", sa.Column("currency_code", sa.String(length=3), nullable=True))
    op.add_column("factures", sa.Column("currency_symbol", sa.String(length=8), nullable=True))
    op.execute("UPDATE factures SET currency_code = 'TND', currency_symbol = 'DT' WHERE currency_code IS NULL")


def downgrade() -> None:
    op.drop_column("factures", "currency_symbol")
    op.drop_column("factures", "currency_code")
