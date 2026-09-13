"""Empêche les doubles remplacements concurrents d'un même rendez-vous."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260913_replanification_concurrency"
down_revision: Union[str, None] = "20260913_add_recruitment_inbound_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Préserve les lignes historiques mais détache les doublons actifs les plus
    # récents afin que la contrainte puisse être installée sans suppression.
    op.execute(sa.text("""
        UPDATE rendez_vous AS duplicate
        SET remplace_rdv_id = NULL,
            statut = CASE WHEN duplicate.statut = 'planifie' THEN 'annule' ELSE duplicate.statut END,
            notes_post_acte = COALESCE(duplicate.notes_post_acte || E'\\n', '') || 'Doublon de replanification neutralisé lors de la migration de concurrence.'
        WHERE duplicate.remplace_rdv_id IS NOT NULL
          AND duplicate.id NOT IN (
              SELECT MIN(kept.id)
              FROM rendez_vous AS kept
              WHERE kept.remplace_rdv_id IS NOT NULL
              GROUP BY kept.remplace_rdv_id
          )
    """))
    op.create_unique_constraint(
        "uq_rendez_vous_remplace_rdv_id",
        "rendez_vous",
        ["remplace_rdv_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_rendez_vous_remplace_rdv_id", "rendez_vous", type_="unique")
