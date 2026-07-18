"""Ajout table signalement (modération Communauté).

Revision ID: 0114
Revises: 0113
Create Date: 2026-07-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0114"
down_revision = "0113"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "signalement",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cible_type", sa.String(), nullable=False, index=True),
        sa.Column("cible_id", sa.Integer(), nullable=False, index=True),
        sa.Column("apercu", sa.String(), nullable=False, server_default=""),
        sa.Column("auteur_cible_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
        sa.Column("signale_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("motif", sa.String(), nullable=False),
        sa.Column("statut", sa.String(), nullable=False, server_default="en_attente"),
        sa.Column("cree_le", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("traite_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
        sa.Column("traite_le", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("signalement")
