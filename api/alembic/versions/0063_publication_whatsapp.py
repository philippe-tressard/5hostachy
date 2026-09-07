"""Ajout colonne partager_whatsapp sur publication

Revision ID: 0063
Revises: 0062
"""
from alembic import op
import sqlalchemy as sa

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "publication",
        sa.Column("partager_whatsapp", sa.Boolean, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("publication", "partager_whatsapp")
