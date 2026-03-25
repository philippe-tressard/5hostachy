"""Ajout frequence_type et frequence_valeur sur evenement

Revision ID: 0060
Revises: 0059
"""
from alembic import op
import sqlalchemy as sa

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evenement") as batch_op:
        batch_op.add_column(sa.Column("frequence_type", sa.String, nullable=True))
        batch_op.add_column(sa.Column("frequence_valeur", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("evenement") as batch_op:
        batch_op.drop_column("frequence_valeur")
        batch_op.drop_column("frequence_type")
