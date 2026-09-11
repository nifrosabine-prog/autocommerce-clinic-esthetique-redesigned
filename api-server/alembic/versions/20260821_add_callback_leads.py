"""Add tenant-scoped callback leads.

Revision ID: 20260821_callback_leads
"""
from alembic import op
import sqlalchemy as sa

revision = "20260821_callback_leads_aesthetic"
down_revision = "20260820_dossier_facture"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic crée historiquement version_num en VARCHAR(32), alors que ce
    # revision ID métier contient 33 caractères. Élargir avant que le runner
    # Alembic n’écrive le nouveau head dans la table de version.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")

    op.create_table(
        "callback_leads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(length=100), nullable=False),
        sa.Column("telephone", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="landing"),
        sa.Column("statut", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("assigned_to_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("contacted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_callback_leads_clinic_id", "callback_leads", ["clinic_id"])
    op.create_index("ix_callback_leads_telephone", "callback_leads", ["telephone"])
    op.create_index("ix_callback_leads_statut", "callback_leads", ["statut"])


def downgrade() -> None:
    op.drop_index("ix_callback_leads_statut", table_name="callback_leads")
    op.drop_index("ix_callback_leads_telephone", table_name="callback_leads")
    op.drop_index("ix_callback_leads_clinic_id", table_name="callback_leads")
    op.drop_table("callback_leads")
