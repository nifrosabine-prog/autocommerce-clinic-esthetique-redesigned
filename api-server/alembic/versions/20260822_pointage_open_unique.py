"""Prevent multiple open attendance records per tenant and user.

Revision ID: 20260822_pointage_open_unique
Revises: 20260822_add_mfa_challenges
"""
from alembic import op

revision = "20260822_pointage_open_unique"
down_revision = "20260822_add_mfa_challenges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep the most recent open record when legacy duplicates exist, then add
    # the invariant at the database boundary.
    op.execute(
        """
        DELETE FROM pointages
        WHERE fin IS NULL
          AND EXISTS (
              SELECT 1 FROM pointages newer
              WHERE newer.id > pointages.id
                AND newer.clinic_id = pointages.clinic_id
                AND newer.utilisateur_id = pointages.utilisateur_id
                AND newer.fin IS NULL
          )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_pointages_open_user_clinic
        ON pointages (clinic_id, utilisateur_id)
        WHERE fin IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_pointages_open_user_clinic")
