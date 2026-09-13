"""Add postes table and optional AI CV analysis fields on candidatures.

Revision ID: 20260828_recrutement_postes_ia
Revises: 20260826_workflow_audit_status_length
Create Date: 2026-08-28

Additive only: no existing column is renamed or dropped, so the historical
free-text ``candidatures.poste`` field keeps working exactly as before.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_recrutement_postes_ia"
down_revision: Union[str, None] = "20260826_workflow_audit_status_length"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "postes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("titre", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("statut", sa.String(length=20), nullable=False, server_default="ouvert"),
        sa.Column(
            "cree_par_id",
            sa.Integer(),
            sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("ferme_le", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_postes_clinic_id", "postes", ["clinic_id"])
    op.create_index("ix_postes_statut", "postes", ["statut"])

    with op.batch_alter_table("candidatures", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("poste_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_candidatures_poste_id_postes", "postes", ["poste_id"], ["id"], ondelete="SET NULL")
        batch_op.add_column(sa.Column("analyse_ia_statut", sa.String(length=20), nullable=False, server_default="non_demandee"))
        batch_op.add_column(sa.Column("analyse_ia_resume", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("analyse_ia_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("analyse_ia_le", sa.DateTime(), nullable=True))
    op.create_index("ix_candidatures_poste_id", "candidatures", ["poste_id"])


def downgrade() -> None:
    op.drop_index("ix_candidatures_poste_id", table_name="candidatures")
    with op.batch_alter_table("candidatures", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_candidatures_poste_id_postes", type_="foreignkey")
        batch_op.drop_column("analyse_ia_le")
        batch_op.drop_column("analyse_ia_score")
        batch_op.drop_column("analyse_ia_resume")
        batch_op.drop_column("analyse_ia_statut")
        batch_op.drop_column("poste_id")

    op.drop_index("ix_postes_statut", table_name="postes")
    op.drop_index("ix_postes_clinic_id", table_name="postes")
    op.drop_table("postes")
