"""Add the clinic team audit trail.

Revision ID: 20260904_team_audit
Revises: 20260903_alertes_stock
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260904_team_audit"
down_revision: Union[str, None] = "20260903_alertes_stock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs_team",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("valeur_avant", sa.JSON(), nullable=True),
        sa.Column("valeur_apres", sa.JSON(), nullable=True),
        sa.Column("modifie_par_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["modifie_par_id"], ["utilisateurs.id"]),
    )
    op.create_index("ix_audit_logs_team_clinic_id", "audit_logs_team", ["clinic_id"])
    op.create_index("ix_audit_logs_team_utilisateur_id", "audit_logs_team", ["utilisateur_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_team_utilisateur_id", table_name="audit_logs_team")
    op.drop_index("ix_audit_logs_team_clinic_id", table_name="audit_logs_team")
    op.drop_table("audit_logs_team")