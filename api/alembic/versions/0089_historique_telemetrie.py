"""Historique des exécutions d'agrégation de la télémétrie.

Revision ID: 0089
Revises: 0088
Create Date: 2026-04-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historique_telemetrie",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("declenchee_par", sa.String, nullable=False, server_default="cron"),
        sa.Column("statut", sa.String, nullable=False, server_default="en_cours"),
        sa.Column("jours_agreges", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mois_agreges", sa.Integer, nullable=False, server_default="0"),
        sa.Column("events_purges", sa.Integer, nullable=False, server_default="0"),
        sa.Column("daily_purges", sa.Integer, nullable=False, server_default="0"),
        sa.Column("monthly_purges", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duree_secondes", sa.Float, nullable=True),
        sa.Column("erreur", sa.String, nullable=True),
        sa.Column("cree_le", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("terminee_le", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("historique_telemetrie")
