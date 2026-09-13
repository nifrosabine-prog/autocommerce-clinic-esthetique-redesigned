"""Trace l'identifiant Resend d'une candidature reçue par e-mail."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20260913_add_recruitment_inbound_source"
down_revision: Union[str, None] = "20260912_add_cv_texte_extrait"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidatures", sa.Column("source_email_id", sa.String(length=100), nullable=True))
    op.create_unique_constraint("uq_candidatures_source_email_id", "candidatures", ["source_email_id"])


def downgrade() -> None:
    op.drop_constraint("uq_candidatures_source_email_id", "candidatures", type_="unique")
    op.drop_column("candidatures", "source_email_id")
