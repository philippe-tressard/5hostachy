"""Initial migration — creation of all tables

Revision ID: 0001
Revises:
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLModel creates all tables via create_db_and_tables() on first start.
    # This migration is intentionally a no-op for the initial state.
    # Future schema changes should be generated with: alembic revision --autogenerate
    pass


def downgrade() -> None:
    pass
