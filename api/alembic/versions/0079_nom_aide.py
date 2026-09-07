"""Ajout nom_aide / prenom_aide pour aidant et mandataire

Revision ID: 0079
Revises: 0078
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("utilisateur", sa.Column("nom_aide", sa.String(), nullable=True))
    op.add_column("utilisateur", sa.Column("prenom_aide", sa.String(), nullable=True))


def downgrade():
    op.drop_column("utilisateur", "prenom_aide")
    op.drop_column("utilisateur", "nom_aide")
