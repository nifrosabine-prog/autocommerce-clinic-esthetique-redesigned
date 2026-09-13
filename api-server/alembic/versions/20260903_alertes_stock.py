"""rappels persistants de seuil stock

Revision ID: 20260903_alertes_stock
Revises: 20260903_stock_lot_mouvements
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260903_alertes_stock"
down_revision: Union[str, None] = "20260903_stock_lot_mouvements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alertes_stock",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinic_id", sa.Integer(), nullable=False),
        sa.Column("type_article", sa.String(20), nullable=False),
        sa.Column("produit_id", sa.Integer(), nullable=True),
        sa.Column("lot_id", sa.Integer(), nullable=True),
        sa.Column("consommable_id", sa.Integer(), nullable=True),
        sa.Column("niveau", sa.String(20), nullable=False),
        sa.Column("article_nom", sa.String(200), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("stock_actuel", sa.Numeric(10, 2), nullable=False),
        sa.Column("seuil", sa.Numeric(10, 2), nullable=False),
        sa.Column("statut", sa.String(20), nullable=False, server_default="active"),
        sa.Column("declenchee_le", sa.DateTime(), nullable=False),
        sa.Column("acquittee_le", sa.DateTime(), nullable=True),
        sa.Column("acquittee_par_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_alertes_stock_clinic_id", "alertes_stock", ["clinic_id"])
    op.create_index("ix_alertes_stock_active_article", "alertes_stock", ["clinic_id", "type_article", "produit_id", "lot_id", "consommable_id", "statut"])


def downgrade() -> None:
    op.drop_index("ix_alertes_stock_active_article", table_name="alertes_stock")
    op.drop_index("ix_alertes_stock_clinic_id", table_name="alertes_stock")
    op.drop_table("alertes_stock")
