"""Ajout colonne cree_le sur devis_prestataire.

Revision ID: 0096
Revises: 0095
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devis_prestataire",
        sa.Column("cree_le", sa.DateTime, nullable=True),
    )
    # Backfill: existing rows get current UTC time as fallback
    op.execute(
        sa.text("UPDATE devis_prestataire SET cree_le = :now WHERE cree_le IS NULL").bindparams(
            now=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        )
    )


def downgrade() -> None:
    op.drop_column("devis_prestataire", "cree_le")
