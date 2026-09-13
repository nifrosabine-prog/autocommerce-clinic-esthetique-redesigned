"""Bloc C — prescriptions médicales.

Revision ID: 20260910_prescriptions_medicales
Revises: 20260910_patient_medical_facts
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260910_prescriptions_medicales"
down_revision: Union[str, None] = "20260910_patient_medical_facts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prescriptions_medicales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("episode_id", sa.Integer(), sa.ForeignKey("episodes_patient.id", ondelete="SET NULL")),
        sa.Column("consultation_id", sa.Integer(), sa.ForeignKey("consultations_medicales.id", ondelete="SET NULL")),
        sa.Column("intervention_id", sa.Integer(), sa.ForeignKey("interventions.id", ondelete="SET NULL")),
        sa.Column("acte_id", sa.Integer(), sa.ForeignKey("actes_medicaux.id", ondelete="SET NULL")),
        sa.Column("prescripteur_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("date_prescription", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("details_enc", sa.Text(), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("classification", sa.String(40), nullable=False, server_default="MEDICAL_SENSITIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    for name, columns in {
        "ix_prescriptions_clinic_id": ["clinic_id"], "ix_prescriptions_patient_id": ["patient_id"],
        "ix_prescriptions_episode_id": ["episode_id"], "ix_prescriptions_consultation_id": ["consultation_id"],
        "ix_prescriptions_intervention_id": ["intervention_id"], "ix_prescriptions_acte_id": ["acte_id"],
        "ix_prescriptions_prescripteur_id": ["prescripteur_id"], "ix_prescriptions_statut": ["statut"],
        "ix_prescriptions_clinic_patient_date": ["clinic_id", "patient_id", "date_prescription"],
    }.items():
        op.create_index(name, "prescriptions_medicales", columns)


def downgrade() -> None:
    for name in (
        "ix_prescriptions_clinic_patient_date", "ix_prescriptions_statut", "ix_prescriptions_prescripteur_id",
        "ix_prescriptions_acte_id", "ix_prescriptions_intervention_id", "ix_prescriptions_consultation_id",
        "ix_prescriptions_episode_id", "ix_prescriptions_patient_id", "ix_prescriptions_clinic_id",
    ):
        op.drop_index(name, table_name="prescriptions_medicales")
    op.drop_table("prescriptions_medicales")
