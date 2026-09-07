"""Ajout contacts_json sur prestataire et table notation_prestataire

Revision ID: 0080
Revises: 0079
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade():
    # contacts_json sur prestataire
    op.add_column("prestataire", sa.Column("contacts_json", sa.Text(), nullable=True))

    # table notation_prestataire
    op.create_table(
        "notation_prestataire",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prestataire_id", sa.Integer(), sa.ForeignKey("prestataire.id"), nullable=False),
        sa.Column("note", sa.Integer(), nullable=False),
        sa.Column("commentaire", sa.Text(), nullable=True),
        sa.Column("devis_id", sa.Integer(), sa.ForeignKey("devis_prestataire.id"), nullable=True),
        sa.Column("contrat_id", sa.Integer(), sa.ForeignKey("contrat_entretien.id"), nullable=True),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("cree_le", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("notation_prestataire")
    op.drop_column("prestataire", "contacts_json")
