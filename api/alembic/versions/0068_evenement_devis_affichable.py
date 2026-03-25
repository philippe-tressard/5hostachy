"""Ajout colonne affichable sur evenement et devis_prestataire

Revision ID: 0068
Revises: 0067
Create Date: 2025-07-14
"""
from alembic import op

revision = '0068'
down_revision = '0067'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE evenement ADD COLUMN affichable BOOLEAN NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE devis_prestataire ADD COLUMN affichable BOOLEAN NOT NULL DEFAULT 0")


def downgrade():
    pass
