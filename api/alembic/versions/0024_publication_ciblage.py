"""Ajout perimetre_cible et public_cible sur publication

Revision ID: 0024
Revises: 0023
Create Date: 2026-03-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("publication") as batch_op:
        batch_op.add_column(sa.Column("perimetre_cible", sa.String(), nullable=True, server_default='["résidence"]'))
        batch_op.add_column(sa.Column("public_cible", sa.String(), nullable=True, server_default='["résidents"]'))


def downgrade():
    with op.batch_alter_table("publication") as batch_op:
        batch_op.drop_column("public_cible")
        batch_op.drop_column("perimetre_cible")
