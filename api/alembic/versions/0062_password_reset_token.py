"""Création de la table password_reset_token

Revision ID: 0062
Revises: 0061
"""
from alembic import op
import sqlalchemy as sa

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("token", sa.String, nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("used", sa.Boolean, nullable=False, server_default="0"),
    )
    op.create_index("ix_password_reset_token_token", "password_reset_token", ["token"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_token_token", "password_reset_token")
    op.drop_table("password_reset_token")
