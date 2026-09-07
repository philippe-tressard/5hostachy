"""Ajout perimetre_cible sur ticket

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("ticket") as batch_op:
        batch_op.add_column(sa.Column("perimetre_cible", sa.String(), nullable=True, server_default='["résidence"]'))


def downgrade():
    with op.batch_alter_table("ticket") as batch_op:
        batch_op.drop_column("perimetre_cible")
