"""Ajout colonnes notification (WA/syndic/CS) sur evenement et sondage.

Revision ID: 0099
Revises: 0098
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("evenement", "sondage"):
        op.add_column(table, sa.Column("partager_whatsapp", sa.Boolean, nullable=False, server_default=sa.false()))
        op.add_column(table, sa.Column("envoyer_syndic", sa.Boolean, nullable=False, server_default=sa.false()))
        op.add_column(table, sa.Column("envoyer_cs", sa.Boolean, nullable=False, server_default=sa.false()))


def downgrade() -> None:
    for table in ("evenement", "sondage"):
        op.drop_column(table, "envoyer_cs")
        op.drop_column(table, "envoyer_syndic")
        op.drop_column(table, "partager_whatsapp")
