"""Ajout vérification email — colonne email_verifie + table email_verification_token

Revision ID: 0078
Revises: 0077
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "utilisateur",
        sa.Column("email_verifie", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    # Les comptes déjà actifs sont considérés comme vérifiés
    op.execute("UPDATE utilisateur SET email_verifie = 1 WHERE actif = 1")

    op.create_table(
        "email_verification_token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("token", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade():
    op.drop_table("email_verification_token")
    op.drop_column("utilisateur", "email_verifie")
