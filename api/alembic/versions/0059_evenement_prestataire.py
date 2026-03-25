"""Ajout prestataire_id sur evenement + type maintenance_recurrente

Revision ID: 0059
Revises: 0058
"""
from alembic import op
import sqlalchemy as sa

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evenement") as batch_op:
        batch_op.add_column(sa.Column("prestataire_id", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("evenement") as batch_op:
        batch_op.drop_column("prestataire_id")
