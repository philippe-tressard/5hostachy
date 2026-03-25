"""Création de la table devis_prestataire

Revision ID: 0054
Revises: 0053
"""
from alembic import op
import sqlalchemy as sa

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devis_prestataire",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("copropriete_id", sa.Integer, sa.ForeignKey("copropriete.id"), nullable=False),
        sa.Column("prestataire_id", sa.Integer, sa.ForeignKey("prestataire.id"), nullable=False),
        sa.Column("titre", sa.String, nullable=False),
        sa.Column("date_prestation", sa.Date, nullable=True),
        sa.Column("montant_estime", sa.Float, nullable=True),
        sa.Column("statut", sa.String, nullable=False, server_default="en_attente"),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("actif", sa.Boolean, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_table("devis_prestataire")
