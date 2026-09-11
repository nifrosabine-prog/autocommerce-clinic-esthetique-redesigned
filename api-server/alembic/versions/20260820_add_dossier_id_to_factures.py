"""Link invoices to medical dossiers to prevent duplicate billing.

Revision ID: 20260820_dossier_facture
Revises: e8f9a0b1c2d3
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260820_dossier_facture"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "factures",
        sa.Column("dossier_id", sa.Integer(), nullable=True),
    )
    with op.batch_alter_table("factures") as batch_op:
        batch_op.create_foreign_key(
            "fk_factures_dossier_id",
            "dossiers_medicaux",
            ["dossier_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_factures_dossier_id",
        "factures",
        ["dossier_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_factures_dossier_id", table_name="factures")
    with op.batch_alter_table("factures") as batch_op:
        batch_op.drop_constraint("fk_factures_dossier_id", type_="foreignkey")
        batch_op.drop_column("dossier_id")
