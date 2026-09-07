"""Ajout frequence_type et frequence_valeur sur devis_prestataire

Revision ID: 0061
Revises: 0060
"""
from alembic import op
import sqlalchemy as sa

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devis_prestataire") as batch_op:
        batch_op.add_column(sa.Column("frequence_type", sa.String, nullable=True))
        batch_op.add_column(sa.Column("frequence_valeur", sa.Integer, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("devis_prestataire") as batch_op:
        batch_op.drop_column("frequence_valeur")
        batch_op.drop_column("frequence_type")
