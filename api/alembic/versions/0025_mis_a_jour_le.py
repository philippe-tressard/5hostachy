"""Ajout mis_a_jour_le sur publication et evenement

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("publication") as batch_op:
        batch_op.add_column(sa.Column("mis_a_jour_le", sa.DateTime(), nullable=True))

    with op.batch_alter_table("evenement") as batch_op:
        batch_op.add_column(sa.Column("mis_a_jour_le", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("publication") as batch_op:
        batch_op.drop_column("mis_a_jour_le")

    with op.batch_alter_table("evenement") as batch_op:
        batch_op.drop_column("mis_a_jour_le")
