"""Contrat entretien : lien vers un document bibliothèque (document_id)

Revision ID: 0022
Revises: 0021
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contrat_entretien") as batch_op:
        batch_op.add_column(sa.Column("document_id", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("contrat_entretien") as batch_op:
        batch_op.drop_column("document_id")
