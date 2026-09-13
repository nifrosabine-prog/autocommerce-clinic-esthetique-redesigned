"""Bloc 1 — ajustements post-revue (rdv/salle sur Intervention,
PaiementAffectation, versionnage des devis, statut A_VALIDER, notes
protégées). Additif uniquement, aucune donnée existante déplacée.

Revision ID: 20260908_episode_core_adjustments
Revises: 20260907_episode_core
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260908_episode_core_adjustments"
down_revision: Union[str, None] = "20260907_episode_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    # ── 1. rdv_id / salle_id / dates prévues sur Intervention ──────────
    op.add_column("interventions", sa.Column("rdv_id", sa.Integer(), nullable=True))
    op.add_column("interventions", sa.Column("salle_id", sa.Integer(), nullable=True))
    op.add_column("interventions", sa.Column("date_debut_prevue", sa.DateTime(), nullable=True))
    op.add_column("interventions", sa.Column("date_fin_prevue", sa.DateTime(), nullable=True))
    if not _is_sqlite():
        op.create_foreign_key("fk_interventions_rdv_id", "interventions", "rendez_vous", ["rdv_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_interventions_salle_id", "interventions", "salles", ["salle_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_intervention_rdv", "interventions", ["rdv_id"])

    # ── 2. PaiementAffectation (répartition d'un paiement par ligne) ───
    op.create_table(
        "paiements_affectations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("paiement_id", sa.Integer(), nullable=False),
        sa.Column("facture_ligne_id", sa.Integer(), nullable=False),
        sa.Column("montant_affecte", sa.Numeric(10, 3), nullable=False),
        sa.ForeignKeyConstraint(["paiement_id"], ["paiements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facture_ligne_id"], ["facture_lignes.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("paiement_id", "facture_ligne_id", name="uq_paiement_affectation_paiement_ligne"),
        sa.CheckConstraint("montant_affecte > 0", name="ck_paiement_affectation_montant_positif"),
    )
    op.create_index("ix_paiement_affectation_paiement", "paiements_affectations", ["paiement_id"])
    op.create_index("ix_paiement_affectation_ligne", "paiements_affectations", ["facture_ligne_id"])

    # ── 3. Versionnage des devis ────────────────────────────────────────
    op.add_column("devis", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("devis", sa.Column("devis_parent_id", sa.Integer(), nullable=True))
    op.add_column("devis", sa.Column("remplace_devis_id", sa.Integer(), nullable=True))
    if not _is_sqlite():
        op.create_foreign_key("fk_devis_devis_parent_id", "devis", "devis", ["devis_parent_id"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_devis_remplace_devis_id", "devis", "devis", ["remplace_devis_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_devis_parent", "devis", ["devis_parent_id"])

    # ── 5. Statut A_VALIDER — aucune colonne à ajouter (String(20) libre,
    # pas de CHECK constraint sur les valeurs), seule la couche service
    # (Bloc 4) doit connaître la nouvelle valeur. Rien à migrer ici.

    # ── 6. Notes : RESTRICT au lieu de CASCADE + archivage ──────────────
    op.add_column("notes_privees", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("notes_privees", sa.Column("archived_by_id", sa.Integer(), nullable=True))
    if not _is_sqlite():
        op.create_foreign_key("fk_notes_privees_archived_by_id", "notes_privees", "utilisateurs", ["archived_by_id"], ["id"], ondelete="SET NULL")
    # Les FK episode_id/intervention_id ont été créées en CASCADE par la
    # migration précédente (20260907) sans nom explicite → Postgres leur a
    # donné le nom par défaut <table>_<colonne>_fkey. On les remplace par
    # des FK nommées en RESTRICT. À vérifier avant exécution en prod si le
    # nom généré diffère (ex. table déjà migrée manuellement) :
    #   SELECT conname FROM pg_constraint WHERE conrelid = 'notes_privees'::regclass;
    if not _is_sqlite():
        op.drop_constraint("notes_privees_episode_id_fkey", "notes_privees", type_="foreignkey")
        op.create_foreign_key("fk_notes_privees_episode_id", "notes_privees", "episodes_patient", ["episode_id"], ["id"], ondelete="RESTRICT")
        op.drop_constraint("notes_privees_intervention_id_fkey", "notes_privees", type_="foreignkey")
        op.create_foreign_key("fk_notes_privees_intervention_id", "notes_privees", "interventions", ["intervention_id"], ["id"], ondelete="RESTRICT")

    op.add_column("notes_partagees", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("notes_partagees", sa.Column("archived_by_id", sa.Integer(), nullable=True))
    if not _is_sqlite():
        op.create_foreign_key("fk_notes_partagees_archived_by_id", "notes_partagees", "utilisateurs", ["archived_by_id"], ["id"], ondelete="SET NULL")
        op.drop_constraint("notes_partagees_episode_id_fkey", "notes_partagees", type_="foreignkey")
        op.create_foreign_key("fk_notes_partagees_episode_id", "notes_partagees", "episodes_patient", ["episode_id"], ["id"], ondelete="RESTRICT")

    # ── 7. Rôle PRESTATAIRE — aucune migration nécessaire : `Utilisateur.
    # role` est un String(20) sans CHECK constraint sur les valeurs, et
    # `Utilisateur.specialite` existe déjà. Ajout Python uniquement
    # (models/database.py::RoleEnum.PRESTATAIRE).


def downgrade() -> None:
    if not _is_sqlite():
        op.drop_constraint("fk_notes_partagees_episode_id", "notes_partagees", type_="foreignkey")
        op.create_foreign_key("notes_partagees_episode_id_fkey", "notes_partagees", "episodes_patient", ["episode_id"], ["id"], ondelete="CASCADE")
        op.drop_constraint("fk_notes_partagees_archived_by_id", "notes_partagees", type_="foreignkey")
    op.drop_column("notes_partagees", "archived_by_id")
    op.drop_column("notes_partagees", "archived_at")

    if not _is_sqlite():
        op.drop_constraint("fk_notes_privees_intervention_id", "notes_privees", type_="foreignkey")
        op.create_foreign_key("notes_privees_intervention_id_fkey", "notes_privees", "interventions", ["intervention_id"], ["id"], ondelete="CASCADE")
        op.drop_constraint("fk_notes_privees_episode_id", "notes_privees", type_="foreignkey")
        op.create_foreign_key("notes_privees_episode_id_fkey", "notes_privees", "episodes_patient", ["episode_id"], ["id"], ondelete="CASCADE")
        op.drop_constraint("fk_notes_privees_archived_by_id", "notes_privees", type_="foreignkey")
    op.drop_column("notes_privees", "archived_by_id")
    op.drop_column("notes_privees", "archived_at")

    op.drop_index("ix_devis_parent", table_name="devis")
    if not _is_sqlite():
        op.drop_constraint("fk_devis_remplace_devis_id", "devis", type_="foreignkey")
        op.drop_constraint("fk_devis_devis_parent_id", "devis", type_="foreignkey")
    op.drop_column("devis", "remplace_devis_id")
    op.drop_column("devis", "devis_parent_id")
    op.drop_column("devis", "version")

    op.drop_index("ix_paiement_affectation_ligne", table_name="paiements_affectations")
    op.drop_index("ix_paiement_affectation_paiement", table_name="paiements_affectations")
    op.drop_table("paiements_affectations")

    op.drop_index("ix_intervention_rdv", table_name="interventions")
    if not _is_sqlite():
        op.drop_constraint("fk_interventions_salle_id", "interventions", type_="foreignkey")
        op.drop_constraint("fk_interventions_rdv_id", "interventions", type_="foreignkey")
    op.drop_column("interventions", "date_fin_prevue")
    op.drop_column("interventions", "date_debut_prevue")
    op.drop_column("interventions", "salle_id")
    op.drop_column("interventions", "rdv_id")
