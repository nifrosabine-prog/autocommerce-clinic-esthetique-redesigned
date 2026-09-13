"""Bloc D — patient medical documents.

Revision ID: 20260910_documents_medicaux_patients
Revises: 20260910_prescriptions_medicales
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260910_documents_medicaux_patients"
down_revision: Union[str, None] = "20260910_prescriptions_medicales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents_medicaux_patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("consultation_id", sa.Integer(), sa.ForeignKey("consultations_medicales.id", ondelete="SET NULL")),
        sa.Column("intervention_id", sa.Integer(), sa.ForeignKey("interventions.id", ondelete="SET NULL")),
        sa.Column("importateur_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("nom_original", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False, server_default="EXTERNAL_MEDICAL_DOCUMENT"),
        sa.Column("description_enc", sa.Text()),
        sa.Column("chemin_chiffre", sa.String(700), nullable=False),
        sa.Column("hash_sha256", sa.String(64), nullable=False),
        sa.Column("taille_octets", sa.Integer(), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("deleted_by", sa.Integer()),
    )
    for name, columns in {
        "ix_docs_med_clinic_id": ["clinic_id"], "ix_docs_med_patient_id": ["patient_id"],
        "ix_docs_med_consultation_id": ["consultation_id"], "ix_docs_med_intervention_id": ["intervention_id"],
        "ix_docs_med_importateur_id": ["importateur_id"], "ix_docs_med_statut": ["statut"],
        "ix_documents_medicaux_clinic_patient": ["clinic_id", "patient_id", "statut"],
    }.items():
        op.create_index(name, "documents_medicaux_patients", columns)


def downgrade() -> None:
    for name in ("ix_documents_medicaux_clinic_patient", "ix_docs_med_statut", "ix_docs_med_importateur_id", "ix_docs_med_intervention_id", "ix_docs_med_consultation_id", "ix_docs_med_patient_id", "ix_docs_med_clinic_id"):
        op.drop_index(name, table_name="documents_medicaux_patients")
    op.drop_table("documents_medicaux_patients")
