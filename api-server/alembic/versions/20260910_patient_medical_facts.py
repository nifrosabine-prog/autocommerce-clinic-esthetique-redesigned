"""Bloc B — structured patient medical facts.

Revision ID: 20260910_patient_medical_facts
Revises: 20260910_consultations_medicales
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260910_patient_medical_facts"
down_revision: Union[str, None] = "20260910_consultations_medicales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "patients_faits_medicaux",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("episode_id", sa.Integer(), sa.ForeignKey("episodes_patient.id", ondelete="SET NULL")),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("type_fait", sa.String(40), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False, server_default="MEDICAL_SENSITIVE"),
        sa.Column("donnees_enc", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="MANUAL"),
        sa.Column("verification_status", sa.String(30), nullable=False, server_default="VERIFIED"),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for name, columns in {
        "ix_patient_facts_clinic_id": ["clinic_id"],
        "ix_patient_facts_patient_id": ["patient_id"],
        "ix_patient_facts_episode_id": ["episode_id"],
        "ix_patient_facts_auteur_id": ["auteur_id"],
        "ix_patient_facts_type_fait": ["type_fait"],
        "ix_patient_facts_actif": ["actif"],
        "ix_patient_facts_clinic_patient_type": ["clinic_id", "patient_id", "type_fait"],
    }.items():
        op.create_index(name, "patients_faits_medicaux", columns)


def downgrade() -> None:
    for name in (
        "ix_patient_facts_clinic_patient_type", "ix_patient_facts_actif", "ix_patient_facts_type_fait",
        "ix_patient_facts_auteur_id", "ix_patient_facts_episode_id", "ix_patient_facts_patient_id",
        "ix_patient_facts_clinic_id",
    ):
        op.drop_index(name, table_name="patients_faits_medicaux")
    op.drop_table("patients_faits_medicaux")
