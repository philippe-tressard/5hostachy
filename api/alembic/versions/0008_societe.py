"""Colonne societe sur utilisateur

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("utilisateur")]

    if "societe" not in columns:
        op.add_column("utilisateur", sa.Column("societe", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("utilisateur", "societe")
