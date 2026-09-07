"""Ajout perimetre et batiment_id sur devis_prestataire

Revision ID: 0064
Revises: 0063
"""
from alembic import op
import sqlalchemy as sa

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "devis_prestataire",
        sa.Column("perimetre", sa.String(), nullable=False, server_default="résidence"),
    )
    op.add_column(
        "devis_prestataire",
        sa.Column("batiment_id", sa.Integer, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("devis_prestataire", "batiment_id")
    op.drop_column("devis_prestataire", "perimetre")
