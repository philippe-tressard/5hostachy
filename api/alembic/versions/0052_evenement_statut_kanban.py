"""Ajout du champ statut_kanban à la table evenement

Revision ID: 0052
Revises: 0051
"""
from alembic import op
import sqlalchemy as sa

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evenement") as batch_op:
        batch_op.add_column(sa.Column("statut_kanban", sa.String, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("evenement") as batch_op:
        batch_op.drop_column("statut_kanban")
