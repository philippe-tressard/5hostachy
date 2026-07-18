"""Ajout table reponse_communaute (réponses génériques : idées + petites annonces).

Revision ID: 0112
Revises: 0111
Create Date: 2026-07-18

Table générique factorisée pour les réponses de la Communauté (rubrique='idee'
ou 'annonce'). Les commentaires de sondage restent dans commentaire_sondage.
"""
import sqlalchemy as sa
from alembic import op

revision = "0112"
down_revision = "0111"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reponse_communaute",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rubrique", sa.String(), nullable=False, index=True),
        sa.Column("cible_id", sa.Integer(), nullable=False, index=True),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("contenu", sa.String(), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("reponse_communaute")
