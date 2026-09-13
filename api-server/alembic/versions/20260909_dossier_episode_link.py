"""Link medical dossiers to the single patient episode.
Revision ID: 20260909_dossier_episode_link
Revises: 20260909_facture_devis_link
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision: str = "20260909_dossier_episode_link"
down_revision: Union[str, None] = "20260909_facture_devis_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"

def upgrade() -> None:
    op.add_column("dossiers_medicaux", sa.Column("episode_id", sa.Integer(), nullable=True))
    if not _is_sqlite():
        op.create_foreign_key("fk_dossiers_medicaux_episode_id", "dossiers_medicaux", "episodes_patient", ["episode_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_dossiers_medicaux_episode_id", "dossiers_medicaux", ["episode_id"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_dossiers_medicaux_episode_id", table_name="dossiers_medicaux")
    if not _is_sqlite():
        op.drop_constraint("fk_dossiers_medicaux_episode_id", "dossiers_medicaux", type_="foreignkey")
    op.drop_column("dossiers_medicaux", "episode_id")
