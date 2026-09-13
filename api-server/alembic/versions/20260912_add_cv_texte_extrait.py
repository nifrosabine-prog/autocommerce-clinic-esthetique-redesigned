"""Bloc 2/3 correctif — sépare le texte de CV extrait des notes RH manuelles."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260912_add_cv_texte_extrait"
down_revision: Union[str, None] = "20260912_bloc3_absences_praticiens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidatures", sa.Column("cv_texte_extrait", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("candidatures", "cv_texte_extrait")
