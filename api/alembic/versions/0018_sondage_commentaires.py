"""Crée la table commentaire_sondage

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "commentaire_sondage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sondage_id", sa.Integer(), sa.ForeignKey("sondage.id"), nullable=False),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("contenu", sa.Text(), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("commentaire_sondage")
