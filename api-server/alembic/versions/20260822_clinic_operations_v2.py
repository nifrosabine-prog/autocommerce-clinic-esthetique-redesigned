"""Clinic Operations v2: personnel enrichi, cures, suivis et protocoles."""
from alembic import op
import sqlalchemy as sa

revision = "20260822_clinic_operations_v2"
down_revision = "20260821_callback_leads_aesthetic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("utilisateurs", sa.Column("adresse", sa.String(length=500), nullable=True))
    op.add_column("utilisateurs", sa.Column("date_embauche", sa.Date(), nullable=True))
    op.add_column("utilisateurs", sa.Column("diplomes", sa.JSON(), nullable=True))
    op.add_column("utilisateurs", sa.Column("certifications", sa.JSON(), nullable=True))
    op.add_column("utilisateurs", sa.Column("documents_professionnels", sa.JSON(), nullable=True))
    op.add_column("utilisateurs", sa.Column("notes_internes", sa.Text(), nullable=True))

    op.create_table(
        "cures_traitements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("acte_id", sa.Integer(), sa.ForeignKey("actes_medicaux.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nom", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("zone_anatomique", sa.String(length=100), nullable=True),
        sa.Column("seances_prevues", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("statut", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("prochaine_seance_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("seances_prevues > 0", name="ck_cure_seances_prevues_positive"),
    )
    op.create_index("ix_cures_traitements_clinic_id", "cures_traitements", ["clinic_id"])
    op.create_index("ix_cures_traitements_patient_id", "cures_traitements", ["patient_id"])
    op.create_index("ix_cures_traitements_statut", "cures_traitements", ["statut"])
    op.create_index("ix_cures_clinic_status", "cures_traitements", ["clinic_id", "statut"])

    op.create_table(
        "seances_cures",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("cure_id", sa.Integer(), sa.ForeignKey("cures_traitements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("rendez_vous_id", sa.Integer(), sa.ForeignKey("rendez_vous.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers_medicaux.id", ondelete="SET NULL"), nullable=True),
        sa.Column("praticien_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("planifiee_at", sa.DateTime(), nullable=True),
        sa.Column("realisee_at", sa.DateTime(), nullable=True),
        sa.Column("statut", sa.String(length=30), nullable=False, server_default="a_venir"),
        sa.Column("zone_anatomique", sa.String(length=100), nullable=True),
        sa.Column("produits_lots", sa.JSON(), nullable=True),
        sa.Column("photos_ids", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("suivi_recommande_le", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("clinic_id", "cure_id", "numero", name="uq_seance_cure_numero"),
    )
    op.create_index("ix_seances_cures_clinic_id", "seances_cures", ["clinic_id"])
    op.create_index("ix_seances_cures_cure_id", "seances_cures", ["cure_id"])
    op.create_index("ix_seances_cures_statut", "seances_cures", ["statut"])
    op.create_index("ix_seances_cures_clinic_status", "seances_cures", ["clinic_id", "statut"])

    op.create_table(
        "suivis_post_acte",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers_medicaux.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seance_id", sa.Integer(), sa.ForeignKey("seances_cures.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type_suivi", sa.String(length=60), nullable=False, server_default="controle_post_acte"),
        sa.Column("echeance_at", sa.DateTime(), nullable=False),
        sa.Column("statut", sa.String(length=30), nullable=False, server_default="a_faire"),
        sa.Column("assigne_a_id", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("termine_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_suivis_post_acte_clinic_id", "suivis_post_acte", ["clinic_id"])
    op.create_index("ix_suivis_post_acte_patient_id", "suivis_post_acte", ["patient_id"])
    op.create_index("ix_suivis_post_acte_echeance_at", "suivis_post_acte", ["echeance_at"])
    op.create_index("ix_suivis_post_acte_statut", "suivis_post_acte", ["statut"])
    op.create_index("ix_suivis_clinic_due_status", "suivis_post_acte", ["clinic_id", "echeance_at", "statut"])

    op.create_table(
        "evenements_indesirables",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dossier_id", sa.Integer(), sa.ForeignKey("dossiers_medicaux.id", ondelete="SET NULL"), nullable=True),
        sa.Column("acte_id", sa.Integer(), sa.ForeignKey("actes_medicaux.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seance_id", sa.Integer(), sa.ForeignKey("seances_cures.id", ondelete="SET NULL"), nullable=True),
        sa.Column("survenu_at", sa.DateTime(), nullable=False),
        sa.Column("zone_anatomique", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("gravite", sa.String(length=20), nullable=False, server_default="faible"),
        sa.Column("action_effectuee", sa.Text(), nullable=True),
        sa.Column("praticien_informe", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("suivi", sa.Text(), nullable=True),
        sa.Column("statut", sa.String(length=30), nullable=False, server_default="ouvert"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("gravite in ('faible', 'moderee', 'elevee', 'critique')", name="ck_evenement_gravite"),
    )
    op.create_index("ix_evenements_indesirables_clinic_id", "evenements_indesirables", ["clinic_id"])
    op.create_index("ix_evenements_indesirables_patient_id", "evenements_indesirables", ["patient_id"])
    op.create_index("ix_evenements_indesirables_survenu_at", "evenements_indesirables", ["survenu_at"])
    op.create_index("ix_evenements_indesirables_gravite", "evenements_indesirables", ["gravite"])
    op.create_index("ix_evenements_indesirables_statut", "evenements_indesirables", ["statut"])
    op.create_index("ix_evenements_clinic_status", "evenements_indesirables", ["clinic_id", "statut"])

    op.create_table(
        "protocoles_soins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("acte_id", sa.Integer(), sa.ForeignKey("actes_medicaux.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nom", sa.String(length=200), nullable=False),
        sa.Column("categorie", sa.String(length=80), nullable=False, server_default="esthetique"),
        sa.Column("version", sa.String(length=30), nullable=False, server_default="1.0"),
        sa.Column("etapes_avant", sa.JSON(), nullable=False),
        sa.Column("etapes_pendant", sa.JSON(), nullable=False),
        sa.Column("etapes_apres", sa.JSON(), nullable=False),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("utilisateurs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("clinic_id", "nom", "version", name="uq_protocole_clinic_nom_version"),
    )
    op.create_index("ix_protocoles_soins_clinic_id", "protocoles_soins", ["clinic_id"])
    op.create_index("ix_protocoles_soins_actif", "protocoles_soins", ["actif"])


def downgrade() -> None:
    op.drop_index("ix_protocoles_soins_actif", table_name="protocoles_soins")
    op.drop_index("ix_protocoles_soins_clinic_id", table_name="protocoles_soins")
    op.drop_table("protocoles_soins")

    op.drop_index("ix_evenements_clinic_status", table_name="evenements_indesirables")
    for name in ["ix_evenements_indesirables_statut", "ix_evenements_indesirables_gravite", "ix_evenements_indesirables_survenu_at", "ix_evenements_indesirables_patient_id", "ix_evenements_indesirables_clinic_id"]:
        op.drop_index(name, table_name="evenements_indesirables")
    op.drop_table("evenements_indesirables")

    op.drop_index("ix_suivis_clinic_due_status", table_name="suivis_post_acte")
    for name in ["ix_suivis_post_acte_statut", "ix_suivis_post_acte_echeance_at", "ix_suivis_post_acte_patient_id", "ix_suivis_post_acte_clinic_id"]:
        op.drop_index(name, table_name="suivis_post_acte")
    op.drop_table("suivis_post_acte")

    op.drop_index("ix_seances_cures_clinic_status", table_name="seances_cures")
    for name in ["ix_seances_cures_statut", "ix_seances_cures_cure_id", "ix_seances_cures_clinic_id"]:
        op.drop_index(name, table_name="seances_cures")
    op.drop_table("seances_cures")

    op.drop_index("ix_cures_clinic_status", table_name="cures_traitements")
    for name in ["ix_cures_traitements_statut", "ix_cures_traitements_patient_id", "ix_cures_traitements_clinic_id"]:
        op.drop_index(name, table_name="cures_traitements")
    op.drop_table("cures_traitements")

    for column in ["notes_internes", "documents_professionnels", "certifications", "diplomes", "date_embauche", "adresse"]:
        op.drop_column("utilisateurs", column)
