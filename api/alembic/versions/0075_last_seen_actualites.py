"""Add last_seen_actualites to utilisateur

Revision ID: 0075
Revises: 0074
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("utilisateur", sa.Column("last_seen_actualites", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("utilisateur", "last_seen_actualites")
