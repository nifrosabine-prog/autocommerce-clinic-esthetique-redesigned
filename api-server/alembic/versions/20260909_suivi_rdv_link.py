"""Link post-act follow-ups to confirmed appointments.
Revision ID: 20260909_suivi_rdv_link
Revises: 20260909_dossier_episode_link
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = "20260909_suivi_rdv_link"
down_revision: Union[str, None] = "20260909_dossier_episode_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"

def upgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("suivis_post_acte", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("rdv_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key("fk_suivis_post_acte_rdv_id", "rendez_vous", ["rdv_id"], ["id"], ondelete="SET NULL")
            batch_op.create_index("ix_suivis_post_acte_rdv_id", ["rdv_id"], unique=False)
    else:
        op.add_column("suivis_post_acte", sa.Column("rdv_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_suivis_post_acte_rdv_id", "suivis_post_acte", "rendez_vous", ["rdv_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_suivis_post_acte_rdv_id", "suivis_post_acte", ["rdv_id"], unique=False)

def downgrade() -> None:
    if _is_sqlite():
        with op.batch_alter_table("suivis_post_acte", recreate="always") as batch_op:
            batch_op.drop_index("ix_suivis_post_acte_rdv_id")
            batch_op.drop_constraint("fk_suivis_post_acte_rdv_id", type_="foreignkey")
            batch_op.drop_column("rdv_id")
    else:
        op.drop_index("ix_suivis_post_acte_rdv_id", table_name="suivis_post_acte")
        op.drop_constraint("fk_suivis_post_acte_rdv_id", "suivis_post_acte", type_="foreignkey")
        op.drop_column("suivis_post_acte", "rdv_id")
