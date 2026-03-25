"""Ajout du champ type_prestataire à la table prestataire

Revision ID: 0053
Revises: 0052
"""
from alembic import op
import sqlalchemy as sa

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("prestataire") as batch_op:
        batch_op.add_column(sa.Column("type_prestataire", sa.String, nullable=False, server_default="ponctuel"))


def downgrade() -> None:
    with op.batch_alter_table("prestataire") as batch_op:
        batch_op.drop_column("type_prestataire")
