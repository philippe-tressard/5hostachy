"""Ajout champ archivee sur evenement

Revision ID: 0049
Revises: 0048
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("evenement", sa.Column("archivee", sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("evenement", "archivee")
