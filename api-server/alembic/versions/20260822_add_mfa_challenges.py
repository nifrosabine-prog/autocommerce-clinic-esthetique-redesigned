"""Persist one-time MFA challenges.

Revision ID: 20260822_add_mfa_challenges
Revises: 20260822_clinic_operations_v2
"""
from alembic import op
import sqlalchemy as sa

revision = "20260822_add_mfa_challenges"
down_revision = "20260822_clinic_operations_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mfa_challenges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("utilisateur_id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["utilisateur_id"], ["utilisateurs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jti", name="uq_mfa_challenges_jti"),
    )
    op.create_index("ix_mfa_challenges_jti", "mfa_challenges", ["jti"], unique=False)
    op.create_index("ix_mfa_challenges_expires_at", "mfa_challenges", ["expires_at"], unique=False)
    op.create_index(
        "ix_mfa_challenges_user_expiry",
        "mfa_challenges",
        ["utilisateur_id", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_mfa_challenges_active",
        "mfa_challenges",
        ["jti", "consumed_at", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_mfa_challenges_active", table_name="mfa_challenges")
    op.drop_index("ix_mfa_challenges_user_expiry", table_name="mfa_challenges")
    op.drop_index("ix_mfa_challenges_expires_at", table_name="mfa_challenges")
    op.drop_index("ix_mfa_challenges_jti", table_name="mfa_challenges")
    op.drop_table("mfa_challenges")
