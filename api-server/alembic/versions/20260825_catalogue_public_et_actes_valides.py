"""Catalogue public explicite et contraintes métier des actes.

Revision ID: 20260825_catalogue_public_actes
Revises: 20260822_mfa_secret_text
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_catalogue_public_actes"
down_revision = "20260822_mfa_secret_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    truncate_expression = "substr(ranked.normalized_base, 1, 175)" if is_sqlite else "left(ranked.normalized_base, 175)"

    op.add_column("utilisateurs", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("actes_medicaux", sa.Column("nom_normalise", sa.String(length=200), nullable=True))
    op.add_column("actes_medicaux", sa.Column("is_gratuit", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("actes_medicaux", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()))

    # Les entrées existantes non cohérentes sont sorties de l’offre active et
    # publique. Les doublons historiques reçoivent une clé technique distincte
    # afin qu’aucune ligne ne soit supprimée pendant l’upgrade. Les contraintes
    # s’appliquent ensuite aux actes actifs : un historique archivé peut rester
    # consultable sans empêcher le démarrage de la clinique.
    op.execute(
        sa.text(
            f"""
            WITH ranked AS (
                SELECT
                    id,
                    clinic_id,
                    lower(trim(nom)) AS normalized_base,
                    CASE WHEN prix_base = 0 AND (
                        lower(nom) LIKE '%gratuit%'
                        OR lower(coalesce(description, '')) LIKE '%gratuit%'
                    ) THEN true ELSE false END AS gratuit_explicit,
                    row_number() OVER (
                        PARTITION BY clinic_id, lower(trim(nom))
                        ORDER BY is_active DESC, created_at DESC NULLS LAST, id DESC
                    ) AS duplicate_rank
                FROM actes_medicaux
            )
            UPDATE actes_medicaux AS acte
            SET nom_normalise = CASE
                    WHEN ranked.duplicate_rank = 1 THEN ranked.normalized_base
                    ELSE {truncate_expression} || '--archive-' || acte.id
                END,
                is_gratuit = ranked.gratuit_explicit,
                prix_base = CASE WHEN acte.prix_base < 0 THEN 0 ELSE acte.prix_base END,
                is_active = CASE
                    WHEN ranked.duplicate_rank > 1
                      OR length(trim(acte.nom)) < 2
                      OR length(trim(acte.categorie)) < 2
                      OR acte.duree_minutes < 5
                      OR acte.duree_minutes > 480
                      OR acte.prix_base < 0
                      OR (acte.prix_base = 0 AND NOT ranked.gratuit_explicit)
                    THEN false
                    ELSE acte.is_active
                END,
                is_public = false
            FROM ranked
            WHERE acte.id = ranked.id
            """
        )
    )

    constraints = (
        ("uq_actes_clinic_nom_normalise", "unique", ["clinic_id", "nom_normalise"]),
        ("ck_actes_nom_non_vide", "check", "NOT is_active OR length(trim(nom)) >= 2"),
        ("ck_actes_categorie_non_vide", "check", "NOT is_active OR length(trim(categorie)) >= 2"),
        ("ck_actes_duree_bornee", "check", "NOT is_active OR duree_minutes BETWEEN 5 AND 480"),
        ("ck_actes_prix_non_negatif", "check", "prix_base >= 0"),
        ("ck_actes_prix_ou_gratuit", "check", "NOT is_active OR is_gratuit = true OR prix_base > 0"),
    )

    if is_sqlite:
        with op.batch_alter_table("actes_medicaux") as batch_op:
            batch_op.alter_column("nom_normalise", nullable=False)
            for name, kind, expression in constraints:
                if kind == "unique":
                    batch_op.create_unique_constraint(name, expression)
                else:
                    batch_op.create_check_constraint(name, expression)
    else:
        op.alter_column("actes_medicaux", "nom_normalise", nullable=False)
        for name, kind, expression in constraints:
            if kind == "unique":
                op.create_unique_constraint(name, "actes_medicaux", expression)
            else:
                op.create_check_constraint(name, "actes_medicaux", expression)

    op.create_index("ix_actes_publics", "actes_medicaux", ["clinic_id", "is_active", "is_public"])


def downgrade() -> None:
    op.drop_index("ix_actes_publics", table_name="actes_medicaux")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("actes_medicaux") as batch_op:
            batch_op.drop_constraint("ck_actes_prix_ou_gratuit", type_="check")
            batch_op.drop_constraint("ck_actes_prix_non_negatif", type_="check")
            batch_op.drop_constraint("ck_actes_duree_bornee", type_="check")
            batch_op.drop_constraint("ck_actes_categorie_non_vide", type_="check")
            batch_op.drop_constraint("ck_actes_nom_non_vide", type_="check")
            batch_op.drop_constraint("uq_actes_clinic_nom_normalise", type_="unique")
            batch_op.drop_column("is_public")
            batch_op.drop_column("is_gratuit")
            batch_op.drop_column("nom_normalise")
    else:
        op.drop_constraint("ck_actes_prix_ou_gratuit", "actes_medicaux", type_="check")
        op.drop_constraint("ck_actes_prix_non_negatif", "actes_medicaux", type_="check")
        op.drop_constraint("ck_actes_duree_bornee", "actes_medicaux", type_="check")
        op.drop_constraint("ck_actes_categorie_non_vide", "actes_medicaux", type_="check")
        op.drop_constraint("ck_actes_nom_non_vide", "actes_medicaux", type_="check")
        op.drop_constraint("uq_actes_clinic_nom_normalise", "actes_medicaux", type_="unique")
        op.drop_column("actes_medicaux", "is_public")
        op.drop_column("actes_medicaux", "is_gratuit")
        op.drop_column("actes_medicaux", "nom_normalise")
    op.drop_column("utilisateurs", "is_public")
