"""Add immutable recruitment status history.

Revision ID: 20260831_recrutement_history
Revises: 20260828_recrutement_postes_ia
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260831_recrutement_history"
down_revision: Union[str, None] = "20260828_recrutement_postes_ia"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "historique_candidatures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "candidature_id", sa.Integer(),
            sa.ForeignKey("candidatures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clinic_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ancien_statut", sa.String(length=20), nullable=True),
        sa.Column("nouveau_statut", sa.String(length=20), nullable=False),
        sa.Column("notes_rh", sa.Text(), nullable=True),
        sa.Column("date_entretien", sa.DateTime(), nullable=True),
        sa.Column(
            "change_par_id", sa.Integer(),
            sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_historique_candidatures_clinic_id", "historique_candidatures", ["clinic_id"])
    op.create_index(
        "ix_historique_candidatures_candidature", "historique_candidatures",
        ["candidature_id", "changed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_historique_candidatures_candidature", table_name="historique_candidatures")
    op.drop_index("ix_historique_candidatures_clinic_id", table_name="historique_candidatures")
    op.drop_table("historique_candidatures")
