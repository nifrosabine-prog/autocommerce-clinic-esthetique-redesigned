"""Bloc 1 — rattachements cliniques à l'épisode patient.

Revision ID: 20260909_episode_clinical_links
Revises: 20260908_episode_core_adjustments
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260909_episode_clinical_links"
down_revision: Union[str, None] = "20260908_episode_core_adjustments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _add_links(table: str, columns: list[str], links: list[tuple[str, str, str]], indexes: list[str]) -> None:
    for column in columns:
        op.add_column(table, sa.Column(column, sa.Integer(), nullable=True))
    if not _is_sqlite():
        for name, target, column in links:
            op.create_foreign_key(name, table, target, [column], ["id"], ondelete="SET NULL" if table == "photos_clinic" else "RESTRICT")
    for index in indexes:
        op.create_index(index, table, [index.removeprefix("ix_" ).removesuffix("_episode").removesuffix("_intervention") + "_id"] if False else (["episode_id"] if index.endswith("_episode") else ["intervention_id"]))


def upgrade() -> None:
    _add_links("photos_clinic", ["episode_id", "intervention_id"], [
        ("fk_photos_clinic_episode_id", "episodes_patient", "episode_id"),
        ("fk_photos_clinic_intervention_id", "interventions", "intervention_id"),
    ], ["ix_photos_clinic_episode", "ix_photos_clinic_intervention"])
    _add_links("consentements", ["episode_id", "intervention_id"], [
        ("fk_consentements_episode_id", "episodes_patient", "episode_id"),
        ("fk_consentements_intervention_id", "interventions", "intervention_id"),
    ], ["ix_consentements_episode", "ix_consentements_intervention"])
    _add_links("utilisations_lot", ["episode_id", "intervention_id"], [
        ("fk_utilisations_lot_episode_id", "episodes_patient", "episode_id"),
        ("fk_utilisations_lot_intervention_id", "interventions", "intervention_id"),
    ], ["ix_utilisations_lot_episode", "ix_utilisations_lot_intervention"])
    _add_links("simulations_ia", ["episode_id", "intervention_id"], [
        ("fk_simulations_ia_episode_id", "episodes_patient", "episode_id"),
        ("fk_simulations_ia_intervention_id", "interventions", "intervention_id"),
    ], ["ix_simulations_ia_episode", "ix_simulations_ia_intervention"])
    _add_links("suivis_post_acte", ["episode_id", "intervention_id"], [
        ("fk_suivis_post_acte_episode_id", "episodes_patient", "episode_id"),
        ("fk_suivis_post_acte_intervention_id", "interventions", "intervention_id"),
    ], ["ix_suivis_post_acte_episode", "ix_suivis_post_acte_intervention"])


def _drop_links(table: str, indexes: list[str], columns: list[str], constraints: list[str]) -> None:
    for index in indexes:
        op.drop_index(index, table_name=table)
    if not _is_sqlite():
        for constraint in constraints:
            op.drop_constraint(constraint, table, type_="foreignkey")
    for column in columns:
        op.drop_column(table, column)


def downgrade() -> None:
    _drop_links("suivis_post_acte", ["ix_suivis_post_acte_intervention", "ix_suivis_post_acte_episode"], ["intervention_id", "episode_id"], ["fk_suivis_post_acte_intervention_id", "fk_suivis_post_acte_episode_id"])
    _drop_links("simulations_ia", ["ix_simulations_ia_intervention", "ix_simulations_ia_episode"], ["intervention_id", "episode_id"], ["fk_simulations_ia_intervention_id", "fk_simulations_ia_episode_id"])
    _drop_links("utilisations_lot", ["ix_utilisations_lot_intervention", "ix_utilisations_lot_episode"], ["intervention_id", "episode_id"], ["fk_utilisations_lot_intervention_id", "fk_utilisations_lot_episode_id"])
    _drop_links("consentements", ["ix_consentements_intervention", "ix_consentements_episode"], ["intervention_id", "episode_id"], ["fk_consentements_intervention_id", "fk_consentements_episode_id"])
    _drop_links("photos_clinic", ["ix_photos_clinic_intervention", "ix_photos_clinic_episode"], ["intervention_id", "episode_id"], ["fk_photos_clinic_intervention_id", "fk_photos_clinic_episode_id"])
