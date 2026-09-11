"""Ajoute l’assignation de tâche par rôle métier.

Revision ID: 20260825_task_assignee_role
Revises: 20260825_dossier_brouillon_cloture
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_task_assignee_role"
down_revision = "20260825_dossier_brouillon_cloture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("taches_internes_assistant", sa.Column("assignee_role", sa.String(length=30), nullable=True))
    op.create_index("ix_taches_assistant_assignee_role", "taches_internes_assistant", ["assignee_role"])


def downgrade() -> None:
    op.drop_index("ix_taches_assistant_assignee_role", table_name="taches_internes_assistant")
    op.drop_column("taches_internes_assistant", "assignee_role")
