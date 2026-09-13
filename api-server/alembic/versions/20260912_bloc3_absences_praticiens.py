"""Bloc 3 — absences praticiens et propositions de réaffectation."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260912_bloc3_absences_praticiens"
down_revision: Union[str, None] = "20260910_documents_medicaux_patients"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "absences_praticiens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("praticien_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("debut", sa.DateTime(), nullable=False),
        sa.Column("fin", sa.DateTime(), nullable=False),
        sa.Column("motif", sa.String(300)),
        sa.Column("statut", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_absences_praticiens_clinic", "absences_praticiens", ["clinic_id"])
    op.create_index("ix_absences_praticiens_praticien", "absences_praticiens", ["praticien_id"])
    op.create_table(
        "reaffectations_rdv",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("absence_id", sa.Integer(), sa.ForeignKey("absences_praticiens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rdv_id", sa.Integer(), sa.ForeignKey("rendez_vous.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ancien_praticien_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("praticien_propose_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="SET NULL")),
        sa.Column("statut", sa.String(20), nullable=False, server_default="a_valider"),
        sa.Column("valide_par", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="SET NULL")),
        sa.Column("valide_at", sa.DateTime()),
        sa.UniqueConstraint("rdv_id", name="uq_reaffectations_rdv_rdv"),
    )
    op.create_index("ix_reaffectations_rdv_clinic", "reaffectations_rdv", ["clinic_id"])
    op.create_index("ix_reaffectations_rdv_absence", "reaffectations_rdv", ["absence_id"])
    op.create_table(
        "suggestions_remplacement_rdv",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("rdv_annule_id", sa.Integer(), sa.ForeignKey("rendez_vous.id", ondelete="CASCADE"), nullable=False),
        sa.Column("praticien_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("date_heure_debut", sa.DateTime(), nullable=False),
        sa.Column("date_heure_fin", sa.DateTime(), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, server_default="a_valider"),
        sa.Column("valide_par", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="SET NULL")),
        sa.Column("nouveau_rdv_id", sa.Integer(), sa.ForeignKey("rendez_vous.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_suggestions_remplacement_clinic", "suggestions_remplacement_rdv", ["clinic_id"])
    op.create_index("ix_suggestions_remplacement_rdv", "suggestions_remplacement_rdv", ["rdv_annule_id"])


def downgrade() -> None:
    op.drop_index("ix_suggestions_remplacement_rdv", table_name="suggestions_remplacement_rdv")
    op.drop_index("ix_suggestions_remplacement_clinic", table_name="suggestions_remplacement_rdv")
    op.drop_table("suggestions_remplacement_rdv")
    op.drop_index("ix_reaffectations_rdv_absence", table_name="reaffectations_rdv")
    op.drop_index("ix_reaffectations_rdv_clinic", table_name="reaffectations_rdv")
    op.drop_table("reaffectations_rdv")
    op.drop_index("ix_absences_praticiens_praticien", table_name="absences_praticiens")
    op.drop_index("ix_absences_praticiens_clinic", table_name="absences_praticiens")
    op.drop_table("absences_praticiens")
