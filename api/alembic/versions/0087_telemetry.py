"""Télémétrie : tables telemetry_event, telemetry_daily, telemetry_monthly

Revision ID: 0087
Revises: 0086
Create Date: 2026-04-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telemetry_event",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=True),
        sa.Column("page", sa.String, nullable=False, index=True),
        sa.Column("action", sa.String, nullable=False, server_default="view"),
        sa.Column("detail", sa.String, nullable=True),
        sa.Column("cree_le", sa.DateTime, nullable=False, index=True),
    )

    op.create_table(
        "telemetry_daily",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("jour", sa.String, nullable=False, index=True),
        sa.Column("page", sa.String, nullable=False),
        sa.Column("action", sa.String, nullable=False, server_default="view"),
        sa.Column("utilisateurs_uniques", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "telemetry_monthly",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("mois", sa.String, nullable=False, index=True),
        sa.Column("page", sa.String, nullable=False),
        sa.Column("action", sa.String, nullable=False, server_default="view"),
        sa.Column("utilisateurs_uniques", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("telemetry_monthly")
    op.drop_table("telemetry_daily")
    op.drop_table("telemetry_event")
