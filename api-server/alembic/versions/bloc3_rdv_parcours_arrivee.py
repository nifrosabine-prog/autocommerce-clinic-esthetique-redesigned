"""
AutoCommerce Clinic — Bloc 3 : migration agenda / accueil patient.

Additif et rétrocompatible :
  - colonnes rendez_vous.source, rendez_vous.reference, rendez_vous.remplace_rdv_id ;
  - table rdv_evenements (journal d'événements d'agenda : ancienne valeur,
    nouvelle valeur, auteur, date, motif).
down_revision : bloc2_prestataire_role (fin du Bloc 2).
"""

from alembic import op
import sqlalchemy as sa

revision = "bloc3_rdv_parcours_arrivee"
down_revision = "bloc2_prestataire_role"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    op.add_column("rendez_vous", sa.Column("source", sa.String(20), nullable=True))
    op.add_column("rendez_vous", sa.Column("reference", sa.String(30), nullable=True))
    op.add_column("rendez_vous", sa.Column("remplace_rdv_id", sa.Integer(), nullable=True))
    if not _is_sqlite():
        op.create_foreign_key("fk_rendez_vous_remplace_rdv_id", "rendez_vous", "rendez_vous", ["remplace_rdv_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_rendez_vous_reference", "rendez_vous", ["reference"])
    op.create_index("ix_rendez_vous_source", "rendez_vous", ["source"])

    op.create_table(
        "rdv_evenements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("rdv_id", sa.Integer(), sa.ForeignKey("rendez_vous.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type_evenement", sa.String(30), nullable=False),
        sa.Column("ancienne_valeur", sa.Text(), nullable=True),
        sa.Column("nouvelle_valeur", sa.Text(), nullable=True),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("motif", sa.Text(), nullable=True),
        sa.Column("cree_le", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_rdv_evenements_rdv_id", "rdv_evenements", ["rdv_id"])
    op.create_index("ix_rdv_evenements_clinic_id", "rdv_evenements", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_rdv_evenements_clinic_id", table_name="rdv_evenements")
    op.drop_index("ix_rdv_evenements_rdv_id", table_name="rdv_evenements")
    op.drop_table("rdv_evenements")
    op.drop_index("ix_rendez_vous_source", table_name="rendez_vous")
    op.drop_index("ix_rendez_vous_reference", table_name="rendez_vous")
    if not _is_sqlite():
        op.drop_constraint("fk_rendez_vous_remplace_rdv_id", "rendez_vous", type_="foreignkey")
    op.drop_column("rendez_vous", "remplace_rdv_id")
    op.drop_column("rendez_vous", "reference")
    op.drop_column("rendez_vous", "source")
