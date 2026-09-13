"""Bloc A — consultations médicales structurées.

Revision ID: 20260910_consultations_medicales
Revises: 20260910_devis_dossier_link
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260910_consultations_medicales"
down_revision: Union[str, None] = "20260910_devis_dossier_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = [
    ("motif_enc", sa.Text()), ("demande_patient_enc", sa.Text()), ("objectif_enc", sa.Text()),
    ("histoire_enc", sa.Text()), ("evolution_enc", sa.Text()), ("traitements_precedents_enc", sa.Text()),
    ("contexte_enc", sa.Text()), ("observations_cliniques_enc", sa.Text()), ("mesures_enc", sa.Text()),
    ("diagnostic_enc", sa.Text()), ("indication_enc", sa.Text()), ("contre_indications_enc", sa.Text()),
    ("facteurs_risque_enc", sa.Text()), ("objectifs_therapeutiques_enc", sa.Text()),
    ("benefices_attendus_enc", sa.Text()), ("risques_enc", sa.Text()), ("alternatives_enc", sa.Text()),
    ("plan_therapeutique_enc", sa.Text()), ("recommandation_enc", sa.Text()), ("acte_propose_enc", sa.Text()),
    ("suivi_enc", sa.Text()),
]


def upgrade() -> None:
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("episode_id", sa.Integer(), sa.ForeignKey("episodes_patient.id", ondelete="SET NULL")),
        sa.Column("rdv_id", sa.Integer(), sa.ForeignKey("rendez_vous.id", ondelete="SET NULL")),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("date_consultation", sa.DateTime(), nullable=False),
        sa.Column("type_consultation", sa.String(60), nullable=False, server_default="initiale"),
        *[sa.Column(name, type_) for name, type_ in _COLUMNS],
        sa.Column("prochain_rdv_at", sa.DateTime()),
        sa.Column("statut", sa.String(20), nullable=False, server_default="brouillon"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    ]
    op.create_table("consultations_medicales", *columns)
    op.create_index("ix_consultations_medicales_clinic_id", "consultations_medicales", ["clinic_id"])
    op.create_index("ix_consultations_medicales_patient_id", "consultations_medicales", ["patient_id"])
    op.create_index("ix_consultations_medicales_episode_id", "consultations_medicales", ["episode_id"])
    op.create_index("ix_consultations_medicales_rdv_id", "consultations_medicales", ["rdv_id"])
    op.create_index("ix_consultations_medicales_auteur_id", "consultations_medicales", ["auteur_id"])
    op.create_index("ix_consultations_medicales_date_consultation", "consultations_medicales", ["date_consultation"])
    op.create_index("ix_consultations_patient_date", "consultations_medicales", ["patient_id", "date_consultation"])
    op.create_index("ix_consultations_clinic_episode", "consultations_medicales", ["clinic_id", "episode_id"])


def downgrade() -> None:
    op.drop_index("ix_consultations_clinic_episode", table_name="consultations_medicales")
    op.drop_index("ix_consultations_patient_date", table_name="consultations_medicales")
    for name in ("date_consultation", "auteur_id", "rdv_id", "episode_id", "patient_id", "clinic_id"):
        op.drop_index(f"ix_consultations_medicales_{name}", table_name="consultations_medicales")
    op.drop_table("consultations_medicales")
