"""
AutoCommerce Clinic — Bloc 2 : rôle PRESTATAIRE (masseuse, ...)

Ajoute le rôle `prestataire` à la table `utilisateurs.role`. Le champ est
déjà une String(20) libre : aucune contrainte CHECK n'existait, ce changement
est donc purement additif et rétrocompatible. Les permissions sont portées
par le code (matrice RBAC) et les tests ; aucune donnée n'est migrée.
"""

from alembic import op
import sqlalchemy as sa

revision = "bloc2_prestataire_role"
down_revision = "20260909_episode_clinical_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE utilisateurs SET role = 'prestataire' WHERE role = 'masseuse'")
    # Alembic enregistre lui-même la version dans alembic_version après
    # upgrade : aucune écriture manuelle ici (évite les têtes dupliquées).


def downgrade() -> None:
    # Rétrograde : les prestataires redeviennent des comptes génériques.
    op.execute("UPDATE utilisateurs SET role = 'assistante' WHERE role = 'prestataire'")
