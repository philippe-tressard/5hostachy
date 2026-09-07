"""rename sondage_interdit to communaute_interdit

Revision ID: 0070
Revises: 0069
"""
from alembic import op

revision = "0070"
down_revision = "0069"


def upgrade() -> None:
    op.alter_column("utilisateur", "sondage_interdit", new_column_name="communaute_interdit")


def downgrade() -> None:
    op.alter_column("utilisateur", "communaute_interdit", new_column_name="sondage_interdit")
