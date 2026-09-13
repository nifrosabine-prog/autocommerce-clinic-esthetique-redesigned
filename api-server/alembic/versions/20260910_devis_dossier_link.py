"""Link quotes to the patient medical dossier.

Revision ID: 20260910_devis_dossier_link
Revises: 20260909_suivi_rdv_link
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260910_devis_dossier_link"
down_revision: Union[str, None] = "20260909_suivi_rdv_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("devis", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("dossier_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_devis_dossier_id", "dossiers_medicaux", ["dossier_id"], ["id"], ondelete="RESTRICT"
            )
            batch_op.create_index("ix_devis_dossier_id", ["dossier_id"], unique=False)
    else:
        op.add_column("devis", sa.Column("dossier_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_devis_dossier_id", "devis", "dossiers_medicaux", ["dossier_id"], ["id"], ondelete="RESTRICT"
        )
        op.create_index("ix_devis_dossier_id", "devis", ["dossier_id"], unique=False)


def downgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("devis", recreate="always") as batch_op:
            batch_op.drop_index("ix_devis_dossier_id")
            batch_op.drop_constraint("fk_devis_dossier_id", type_="foreignkey")
            batch_op.drop_column("dossier_id")
    else:
        op.drop_index("ix_devis_dossier_id", table_name="devis")
        op.drop_constraint("fk_devis_dossier_id", "devis", type_="foreignkey")
        op.drop_column("devis", "dossier_id")
