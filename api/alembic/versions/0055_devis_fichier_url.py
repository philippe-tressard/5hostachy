"""Ajout colonne fichier_url sur devis_prestataire

Revision ID: 0055
Revises: 0054
"""
from alembic import op
import sqlalchemy as sa

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devis_prestataire", sa.Column("fichier_url", sa.String, nullable=True))


def downgrade() -> None:
    op.drop_column("devis_prestataire", "fichier_url")
