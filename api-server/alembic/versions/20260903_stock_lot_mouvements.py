"""mouvements lots injectables + traçabilité réceptions

Revision ID: 20260903_stock_lot_mouvements
Revises: 20260902_facture_currency
Create Date: 2026-09-03 10:00:00.000000

Ajoute la table ``mouvements_lots_injectables`` : registre d'audit unique
pour les réceptions (crédit), injections (débit) et ajustements de stock
des lots injectables. Chaque ligne est rattachée à un utilisateur, une
référence (n° de bon de livraison) et un motif.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260903_stock_lot_mouvements"
down_revision: Union[str, None] = "20260902_facture_currency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mouvements_lots_injectables",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column(
            "lot_id",
            sa.Integer(),
            sa.ForeignKey("lots_injectables.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("type_mouvement", sa.String(length=20), nullable=False),
        sa.Column("quantite", sa.Numeric(10, 3), nullable=False),
        sa.Column("date_mouvement", sa.DateTime(), nullable=False),
        sa.Column(
            "utilisateur_id",
            sa.Integer(),
            sa.ForeignKey("utilisateurs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("motif", sa.String(length=255), nullable=True),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("document_url", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_mvt_lot_clinic_date", "mouvements_lots_injectables", ["clinic_id", "date_mouvement"]
    )
    op.create_index("ix_mouvements_lots_lot_id", "mouvements_lots_injectables", ["lot_id"])
    op.create_index("ix_mouvements_lots_clinic_id", "mouvements_lots_injectables", ["clinic_id"])


def downgrade() -> None:
    op.drop_index("ix_mouvements_lots_clinic_id", table_name="mouvements_lots_injectables")
    op.drop_index("ix_mouvements_lots_lot_id", table_name="mouvements_lots_injectables")
    op.drop_index("ix_mvt_lot_clinic_date", table_name="mouvements_lots_injectables")
    op.drop_table("mouvements_lots_injectables")
