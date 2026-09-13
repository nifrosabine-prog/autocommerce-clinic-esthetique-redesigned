"""Link an invoice to one quote for one-time conversion.
Revision ID: 20260909_facture_devis_link
Revises: bloc3_rdv_parcours_arrivee
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = "20260909_facture_devis_link"
down_revision: Union[str, None] = "bloc3_rdv_parcours_arrivee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"

def upgrade() -> None:
    op.add_column("factures", sa.Column("devis_id", sa.Integer(), nullable=True))
    if not _is_sqlite():
        op.create_foreign_key("fk_factures_devis_id", "factures", "devis", ["devis_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_factures_devis_id", "factures", ["devis_id"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_factures_devis_id", table_name="factures")
    if not _is_sqlite():
        op.drop_constraint("fk_factures_devis_id", "factures", type_="foreignkey")
    op.drop_column("factures", "devis_id")
