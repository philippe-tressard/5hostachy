"""Ajout table annonce_hall (annonces affichées dans les halls — Espace CS).

Revision ID: 0115
Revises: 0114
Create Date: 2026-07-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0115"
down_revision = "0114"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "annonce_hall",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titre", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("perimetre_cible", sa.String(), nullable=False, server_default='["résidence"]'),
        sa.Column("format_demande", sa.String(), nullable=False, server_default="auto"),
        sa.Column("format_effectif", sa.String(), nullable=False, server_default="a4"),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("pdf_chemin", sa.String(), nullable=False, server_default=""),
        sa.Column("pdf_nom", sa.String(), nullable=False, server_default=""),
        sa.Column("taille_octets", sa.Integer(), nullable=True),
        sa.Column("destinataires", sa.String(), nullable=False, server_default="[]"),
        sa.Column("envoye_le", sa.DateTime(), nullable=True),
        sa.Column("archivee", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("annonce_hall")
