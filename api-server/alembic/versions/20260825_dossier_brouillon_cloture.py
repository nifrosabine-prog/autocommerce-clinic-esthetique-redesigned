"""Etat clinique des dossiers : brouillon ou clôture.

Revision ID: 20260825_dossier_brouillon_cloture
Revises: 20260825_catalogue_public_actes
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_dossier_brouillon_cloture"
down_revision = "20260825_catalogue_public_actes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("dossiers_medicaux") as batch_op:
            batch_op.add_column(
                sa.Column("statut_clinique", sa.String(length=20), nullable=False, server_default="cloture")
            )
            batch_op.create_check_constraint(
                "ck_dossiers_statut_clinique",
                "statut_clinique IN ('brouillon', 'cloture')",
            )
    else:
        op.add_column(
            "dossiers_medicaux",
            sa.Column("statut_clinique", sa.String(length=20), nullable=False, server_default="cloture"),
        )
        op.create_check_constraint(
            "ck_dossiers_statut_clinique",
            "dossiers_medicaux",
            "statut_clinique IN ('brouillon', 'cloture')",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("dossiers_medicaux") as batch_op:
            batch_op.drop_constraint("ck_dossiers_statut_clinique", type_="check")
            batch_op.drop_column("statut_clinique")
    else:
        op.drop_constraint("ck_dossiers_statut_clinique", "dossiers_medicaux", type_="check")
        op.drop_column("dossiers_medicaux", "statut_clinique")
