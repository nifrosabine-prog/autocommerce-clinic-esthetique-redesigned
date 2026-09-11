"""Instantanés contractuels des consentements spécifiques.

Revision ID: 20260826_consentement_contrat_snapshot
Revises: 20260825_task_assignee_role
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa


revision = "20260826_consentement_contrat_snapshot"
down_revision = "20260825_task_assignee_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("consentements") as batch_op:
        batch_op.add_column(sa.Column("praticien_signataire_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("contrat_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("attestation_praticien", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("signature_praticien_base64", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_consentements_praticien_signataire",
            "utilisateurs",
            ["praticien_signataire_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("consentements") as batch_op:
        batch_op.drop_constraint("fk_consentements_praticien_signataire", type_="foreignkey")
        batch_op.drop_column("attestation_praticien")
        batch_op.drop_column("signature_praticien_base64")
        batch_op.drop_column("contrat_snapshot")
        batch_op.drop_column("praticien_signataire_id")
