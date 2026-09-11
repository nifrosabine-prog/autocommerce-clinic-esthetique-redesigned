"""Add global super-admin subscription registry.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clinic_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("clinic_name", sa.String(length=200), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False, server_default="essentiel"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("monthly_amount", sa.Numeric(precision=10, scale=3), nullable=False, server_default="0.000"),
        sa.Column("max_users", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_payment_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clinic_id", name="uq_clinic_subscriptions_clinic_id"),
    )
    op.create_index("ix_clinic_subscriptions_clinic_id", "clinic_subscriptions", ["clinic_id"], unique=False)
    op.create_index("ix_clinic_subscriptions_status", "clinic_subscriptions", ["status"], unique=False)
    op.create_index("ix_clinic_subscriptions_expires_at", "clinic_subscriptions", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clinic_subscriptions_expires_at", table_name="clinic_subscriptions")
    op.drop_index("ix_clinic_subscriptions_status", table_name="clinic_subscriptions")
    op.drop_index("ix_clinic_subscriptions_clinic_id", table_name="clinic_subscriptions")
    op.drop_table("clinic_subscriptions")
