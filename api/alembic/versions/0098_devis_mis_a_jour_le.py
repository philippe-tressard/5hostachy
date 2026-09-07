"""Ajout colonne mis_a_jour_le sur devis_prestataire.

Revision ID: 0098
Revises: 0097
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devis_prestataire",
        sa.Column("mis_a_jour_le", sa.DateTime, nullable=True),
    )
    # Initialiser mis_a_jour_le = cree_le pour les devis existants
    op.execute("UPDATE devis_prestataire SET mis_a_jour_le = cree_le WHERE mis_a_jour_le IS NULL")


def downgrade() -> None:
    op.drop_column("devis_prestataire", "mis_a_jour_le")
