"""Sondage : cloture_forcee + utilisateur sondage_interdit

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sondage") as batch_op:
        batch_op.add_column(sa.Column("cloture_forcee", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    with op.batch_alter_table("utilisateur") as batch_op:
        batch_op.add_column(sa.Column("sondage_interdit", sa.Boolean(), nullable=False, server_default=sa.text("0")))


def downgrade():
    with op.batch_alter_table("utilisateur") as batch_op:
        batch_op.drop_column("sondage_interdit")

    with op.batch_alter_table("sondage") as batch_op:
        batch_op.drop_column("cloture_forcee")
