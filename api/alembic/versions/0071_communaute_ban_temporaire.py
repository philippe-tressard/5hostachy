"""ajout ban temporaire communaute (ban_count + ban_jusqu_au)

Revision ID: 0071
Revises: 0070
"""
import sqlalchemy as sa
from alembic import op

revision = "0071"
down_revision = "0070"


def upgrade() -> None:
    op.add_column("utilisateur", sa.Column("communaute_ban_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("utilisateur", sa.Column("communaute_ban_jusqu_au", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("utilisateur", "communaute_ban_jusqu_au")
    op.drop_column("utilisateur", "communaute_ban_count")
