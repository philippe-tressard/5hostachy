"""Ajoute profils_autorises et batiments_ids sur sondage

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sondage") as batch_op:
        batch_op.add_column(sa.Column("profils_autorises", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("batiments_ids", sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table("sondage") as batch_op:
        batch_op.drop_column("batiments_ids")
        batch_op.drop_column("profils_autorises")
