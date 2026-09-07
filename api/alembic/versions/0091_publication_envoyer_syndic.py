"""Ajout colonne envoyer_syndic sur publication.

Revision ID: 0091
Revises: 0090
Create Date: 2026-04-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("publication") as batch_op:
        batch_op.add_column(sa.Column("envoyer_syndic", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def downgrade():
    with op.batch_alter_table("publication") as batch_op:
        batch_op.drop_column("envoyer_syndic")
