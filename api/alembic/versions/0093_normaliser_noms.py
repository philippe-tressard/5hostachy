"""Normalise prenom (INITCAP) et nom (UPPER) des utilisateurs existants.

Revision ID: 0093
Revises: 0092
Create Date: 2026-04-14
"""
from alembic import op

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE utilisateur SET prenom = INITCAP(TRIM(prenom)), nom = UPPER(TRIM(nom))")
    op.execute("UPDATE utilisateur SET prenom_aide = INITCAP(TRIM(prenom_aide)) WHERE prenom_aide IS NOT NULL")
    op.execute("UPDATE utilisateur SET nom_aide = UPPER(TRIM(nom_aide)) WHERE nom_aide IS NOT NULL")
    op.execute("UPDATE utilisateur SET nom_proprietaire = UPPER(TRIM(nom_proprietaire)) WHERE nom_proprietaire IS NOT NULL")


def downgrade():
    pass
