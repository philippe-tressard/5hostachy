"""Ajout table historique_email.

Revision ID: 0092
Revises: 0091
Create Date: 2026-04-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "historique_email",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False, index=True),
        sa.Column("destinataire", sa.String(), nullable=False),
        sa.Column("sujet", sa.String(), nullable=False, server_default=""),
        sa.Column("statut", sa.String(), nullable=False, server_default="succes"),
        sa.Column("erreur", sa.String(), nullable=True),
        sa.Column("cree_le", sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade():
    op.drop_table("historique_email")
