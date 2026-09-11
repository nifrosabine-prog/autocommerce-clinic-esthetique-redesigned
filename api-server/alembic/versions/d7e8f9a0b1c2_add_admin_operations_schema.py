"""add admin operations schema

Revision ID: d7e8f9a0b1c2
Revises: c9d0e1f2a3b4
Create Date: 2026-08-19

This migration closes the schema gap introduced by the admin catalogue,
room scheduling, staff clocking and AI masking workflows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "salles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("nom", sa.String(length=100), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_salles_clinic_id", "salles", ["clinic_id"])
    op.create_index("ix_salles_clinic_active", "salles", ["clinic_id", "is_active"])

    op.create_table(
        "utilisateurs_actes",
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.Column("acte_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acte_id"], ["actes_medicaux.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("utilisateur_id", "acte_id"),
    )
    op.create_index("ix_utilisateurs_actes_acte_id", "utilisateurs_actes", ["acte_id"])

    op.create_table(
        "pointages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("clinic_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.Column("debut", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("fin", sa.DateTime(), nullable=True),
        sa.Column("duree_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pointages_clinic_id", "pointages", ["clinic_id"])
    op.create_index("ix_pointages_utilisateur_id", "pointages", ["utilisateur_id"])
    op.create_index("ix_pointages_debut", "pointages", ["debut"])
    op.create_index("ix_pointages_clinic_user_debut", "pointages", ["clinic_id", "utilisateur_id", "debut"])

    op.add_column(
        "rendez_vous",
        sa.Column("salle_id", sa.Integer(), nullable=True),
    )
    with op.batch_alter_table("rendez_vous") as batch_op:
        batch_op.create_foreign_key(
            "fk_rendez_vous_salle_id_salles",
            "salles",
            ["salle_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_rendez_vous_salle_id", "rendez_vous", ["salle_id"])

    op.add_column(
        "simulations_ia",
        sa.Column("url_masque", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "simulations_ia",
        sa.Column("instructions", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("simulations_ia", "instructions")
    op.drop_column("simulations_ia", "url_masque")

    op.drop_index("ix_rendez_vous_salle_id", table_name="rendez_vous")
    with op.batch_alter_table("rendez_vous") as batch_op:
        batch_op.drop_constraint("fk_rendez_vous_salle_id_salles", type_="foreignkey")
        batch_op.drop_column("salle_id")

    op.drop_index("ix_pointages_clinic_user_debut", table_name="pointages")
    op.drop_index("ix_pointages_debut", table_name="pointages")
    op.drop_index("ix_pointages_utilisateur_id", table_name="pointages")
    op.drop_index("ix_pointages_clinic_id", table_name="pointages")
    op.drop_table("pointages")

    op.drop_index("ix_utilisateurs_actes_acte_id", table_name="utilisateurs_actes")
    op.drop_table("utilisateurs_actes")

    op.drop_index("ix_salles_clinic_active", table_name="salles")
    op.drop_index("ix_salles_clinic_id", table_name="salles")
    op.drop_table("salles")
