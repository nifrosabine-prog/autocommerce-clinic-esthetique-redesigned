"""Bloc 1 — cœur épisode patient : nouvelles tables (additif uniquement).

Aucune donnée existante n'est touchée ou déplacée par cette migration —
elle crée seulement le nouveau schéma cible en parallèle de l'existant.
Le basculement des données historiques (dossiers/factures existants vers
des épisodes rétroactifs) est traité séparément au Bloc 13, avec son
propre script réversible et un plan de validation dédié : mélanger les
deux dans une seule migration aurait rendu un rollback partiel dangereux.

Revision ID: 20260907_episode_core
Revises: 20260904_team_audit
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260907_episode_core"
down_revision: Union[str, None] = "20260904_team_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Colonnes ajoutées sur des tables existantes (nullable, sans effet
    # sur les lignes existantes) ──────────────────────────────────────
    op.add_column("actes_medicaux", sa.Column("type_intervention", sa.String(length=20), nullable=True))

    # ── Prospect ──────────────────────────────────────────────────────
    op.create_table(
        "prospects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(length=100), nullable=False),
        sa.Column("prenom", sa.String(length=100), nullable=True),
        sa.Column("telephone", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="inconnue"),
        sa.Column("statut", sa.String(length=20), nullable=False, server_default="nouveau"),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column("assigned_to_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("converti_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["utilisateurs.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "(statut != 'converti') OR (patient_id IS NOT NULL)",
            name="ck_prospect_converti_a_patient_id",
        ),
    )
    op.create_index("ix_prospects_telephone", "prospects", ["telephone"])
    op.create_index("ix_prospects_clinic_statut", "prospects", ["clinic_id", "statut"])

    # ── EpisodePatient ────────────────────────────────────────────────
    op.create_table(
        "episodes_patient",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("rdv_origine_id", sa.Integer(), nullable=True),
        sa.Column("statut", sa.String(length=30), nullable=False, server_default="ouvert"),
        sa.Column("ouvert_par_id", sa.Integer(), nullable=False),
        sa.Column("ouvert_le", sa.DateTime(), nullable=False),
        sa.Column("cloture_le", sa.DateTime(), nullable=True),
        sa.Column("cloture_par_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rdv_origine_id"], ["rendez_vous.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ouvert_par_id"], ["utilisateurs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cloture_par_id"], ["utilisateurs.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "(statut != 'cloture') OR (cloture_le IS NOT NULL AND cloture_par_id IS NOT NULL)",
            name="ck_episode_cloture_complete",
        ),
    )
    op.create_index("ix_episode_clinic_patient", "episodes_patient", ["clinic_id", "patient_id"])
    op.create_index("ix_episode_clinic_statut", "episodes_patient", ["clinic_id", "statut"])

    # ── Intervention ──────────────────────────────────────────────────
    op.create_table(
        "interventions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("professionnel_id", sa.Integer(), nullable=False),
        sa.Column("type_intervention", sa.String(length=20), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False, server_default="planifiee"),
        sa.Column("demarree_le", sa.DateTime(), nullable=True),
        sa.Column("terminee_le", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes_patient.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["professionnel_id"], ["utilisateurs.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_intervention_episode", "interventions", ["episode_id"])
    op.create_index("ix_intervention_professionnel_statut", "interventions", ["professionnel_id", "statut"])

    # ── InterventionActe ──────────────────────────────────────────────
    op.create_table(
        "interventions_actes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("intervention_id", sa.Integer(), nullable=False),
        sa.Column("acte_id", sa.Integer(), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False, server_default="propose"),
        sa.Column("prix_convenu", sa.Numeric(10, 3), nullable=False, server_default="0.000"),
        sa.Column("propose_par_id", sa.Integer(), nullable=False),
        sa.Column("propose_le", sa.DateTime(), nullable=False),
        sa.Column("accepte_medical", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("accepte_medical_par_id", sa.Integer(), nullable=True),
        sa.Column("accepte_medical_le", sa.DateTime(), nullable=True),
        sa.Column("accepte_financier", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("accepte_financier_par_id", sa.Integer(), nullable=True),
        sa.Column("accepte_financier_le", sa.DateTime(), nullable=True),
        sa.Column("paye", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paye_le", sa.DateTime(), nullable=True),
        sa.Column("realise", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("realise_par_id", sa.Integer(), nullable=True),
        sa.Column("realise_le", sa.DateTime(), nullable=True),
        sa.Column("refuse_motif", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["acte_id"], ["actes_medicaux.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["propose_par_id"], ["utilisateurs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["accepte_medical_par_id"], ["utilisateurs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepte_financier_par_id"], ["utilisateurs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["realise_par_id"], ["utilisateurs.id"], ondelete="SET NULL"),
        sa.CheckConstraint("prix_convenu >= 0", name="ck_intervention_acte_prix_non_negatif"),
        sa.CheckConstraint(
            "(realise = false) OR (accepte_medical = true)",
            name="ck_intervention_acte_realise_implique_accepte_medical",
        ),
    )
    op.create_index("ix_intervention_acte_intervention", "interventions_actes", ["intervention_id"])
    op.create_index("ix_intervention_acte_statut", "interventions_actes", ["clinic_id", "statut"])

    # ── Devis / DevisLigne ────────────────────────────────────────────
    op.create_table(
        "devis",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("numero_devis", sa.String(length=50), nullable=False, unique=True),
        sa.Column("statut", sa.String(length=20), nullable=False, server_default="brouillon"),
        sa.Column("cree_par_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("envoye_le", sa.DateTime(), nullable=True),
        sa.Column("reponse_le", sa.DateTime(), nullable=True),
        sa.Column("validite_jours", sa.Integer(), nullable=False, server_default="30"),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes_patient.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cree_par_id"], ["utilisateurs.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_devis_clinic_statut", "devis", ["clinic_id", "statut"])
    op.create_index("ix_devis_numero", "devis", ["numero_devis"])

    op.create_table(
        "devis_lignes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("devis_id", sa.Integer(), nullable=False),
        sa.Column("intervention_acte_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("quantite", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prix_unitaire", sa.Numeric(10, 3), nullable=False),
        sa.Column("remise_pct", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("acceptee", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["devis_id"], ["devis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intervention_acte_id"], ["interventions_actes.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("quantite > 0", name="ck_devis_ligne_quantite_positive"),
        sa.CheckConstraint("prix_unitaire >= 0", name="ck_devis_ligne_prix_non_negatif"),
    )
    op.create_index("ix_devis_ligne_devis", "devis_lignes", ["devis_id"])
    op.create_index("ix_devis_ligne_intervention_acte", "devis_lignes", ["intervention_acte_id"])

    # ── FactureLigne ──────────────────────────────────────────────────
    op.create_table(
        "facture_lignes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("facture_id", sa.Integer(), nullable=False),
        sa.Column("intervention_acte_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("quantite", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("prix_unitaire", sa.Numeric(10, 3), nullable=False),
        sa.Column("remise_pct", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("montant_ligne", sa.Numeric(10, 3), nullable=False),
        sa.ForeignKeyConstraint(["facture_id"], ["factures.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intervention_acte_id"], ["interventions_actes.id"], ondelete="SET NULL"),
        sa.CheckConstraint("quantite > 0", name="ck_facture_ligne_quantite_positive"),
        sa.CheckConstraint("prix_unitaire >= 0", name="ck_facture_ligne_prix_non_negatif"),
    )
    op.create_index("ix_facture_ligne_facture", "facture_lignes", ["facture_id"])
    op.create_index("ix_facture_ligne_intervention_acte", "facture_lignes", ["intervention_acte_id"])

    # ── Paiement ──────────────────────────────────────────────────────
    op.create_table(
        "paiements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("facture_id", sa.Integer(), nullable=False),
        sa.Column("montant", sa.Numeric(10, 3), nullable=False),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("statut", sa.String(length=20), nullable=False, server_default="enregistre"),
        sa.Column("encaisse_par_id", sa.Integer(), nullable=False),
        sa.Column("encaisse_le", sa.DateTime(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["facture_id"], ["factures.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["encaisse_par_id"], ["utilisateurs.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("montant > 0", name="ck_paiement_montant_positif"),
    )
    op.create_index("ix_paiement_facture", "paiements", ["facture_id"])

    # ── NotePrivee / NotePartagee ─────────────────────────────────────
    op.create_table(
        "notes_privees",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("intervention_id", sa.Integer(), nullable=True),
        sa.Column("auteur_id", sa.Integer(), nullable=False),
        sa.Column("contenu_enc", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes_patient.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["auteur_id"], ["utilisateurs.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_note_privee_episode", "notes_privees", ["episode_id"])
    op.create_index("ix_note_privee_intervention", "notes_privees", ["intervention_id"])
    op.create_index("ix_note_privee_auteur", "notes_privees", ["auteur_id"])

    op.create_table(
        "notes_partagees",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("auteur_id", sa.Integer(), nullable=False),
        sa.Column("contenu", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes_patient.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["auteur_id"], ["utilisateurs.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_note_partagee_episode", "notes_partagees", ["episode_id"])
    op.create_index("ix_note_partagee_auteur", "notes_partagees", ["auteur_id"])

    # ── AgendaEvent ───────────────────────────────────────────────────
    op.create_table(
        "agenda_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("type_event", sa.String(length=20), nullable=False, server_default="tache"),
        sa.Column("titre", sa.String(length=200), nullable=False),
        sa.Column("professionnel_id", sa.Integer(), nullable=True),
        sa.Column("rdv_id", sa.Integer(), nullable=True),
        sa.Column("date_debut", sa.DateTime(), nullable=False),
        sa.Column("date_fin", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["professionnel_id"], ["utilisateurs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rdv_id"], ["rendez_vous.id"], ondelete="CASCADE"),
        sa.CheckConstraint("date_fin > date_debut", name="ck_agenda_event_periode_valide"),
    )
    op.create_index("ix_agenda_event_clinic_date", "agenda_events", ["clinic_id", "date_debut"])

    # ── AuditEvent ────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("episode_id", sa.Integer(), nullable=True),
        sa.Column("domaine", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("acteur_id", sa.Integer(), nullable=True),
        sa.Column("cible_type", sa.String(length=50), nullable=False),
        sa.Column("cible_id", sa.Integer(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes_patient.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["acteur_id"], ["utilisateurs.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_event_clinic_date", "audit_events", ["clinic_id", "created_at"])
    op.create_index("ix_audit_event_cible", "audit_events", ["cible_type", "cible_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_event_cible", table_name="audit_events")
    op.drop_index("ix_audit_event_clinic_date", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_agenda_event_clinic_date", table_name="agenda_events")
    op.drop_table("agenda_events")

    op.drop_index("ix_note_partagee_auteur", table_name="notes_partagees")
    op.drop_index("ix_note_partagee_episode", table_name="notes_partagees")
    op.drop_table("notes_partagees")

    op.drop_index("ix_note_privee_auteur", table_name="notes_privees")
    op.drop_index("ix_note_privee_intervention", table_name="notes_privees")
    op.drop_index("ix_note_privee_episode", table_name="notes_privees")
    op.drop_table("notes_privees")

    op.drop_index("ix_paiement_facture", table_name="paiements")
    op.drop_table("paiements")

    op.drop_index("ix_facture_ligne_intervention_acte", table_name="facture_lignes")
    op.drop_index("ix_facture_ligne_facture", table_name="facture_lignes")
    op.drop_table("facture_lignes")

    op.drop_index("ix_devis_ligne_intervention_acte", table_name="devis_lignes")
    op.drop_index("ix_devis_ligne_devis", table_name="devis_lignes")
    op.drop_table("devis_lignes")

    op.drop_index("ix_devis_numero", table_name="devis")
    op.drop_index("ix_devis_clinic_statut", table_name="devis")
    op.drop_table("devis")

    op.drop_index("ix_intervention_acte_statut", table_name="interventions_actes")
    op.drop_index("ix_intervention_acte_intervention", table_name="interventions_actes")
    op.drop_table("interventions_actes")

    op.drop_index("ix_intervention_professionnel_statut", table_name="interventions")
    op.drop_index("ix_intervention_episode", table_name="interventions")
    op.drop_table("interventions")

    op.drop_index("ix_episode_clinic_statut", table_name="episodes_patient")
    op.drop_index("ix_episode_clinic_patient", table_name="episodes_patient")
    op.drop_table("episodes_patient")

    op.drop_index("ix_prospects_clinic_statut", table_name="prospects")
    op.drop_index("ix_prospects_telephone", table_name="prospects")
    op.drop_table("prospects")

    op.drop_column("actes_medicaux", "type_intervention")
