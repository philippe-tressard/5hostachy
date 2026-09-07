"""Ajout table compteur_config (catégories de consommation avec prestataire lié)

Revision ID: 0048
Revises: 0047
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "compteur_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type_compteur", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("prestataire_id", sa.Integer(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["prestataire_id"], ["prestataire.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compteur_config_type_compteur", "compteur_config", ["type_compteur"])

    # Seed the default water counter
    op.execute(
        "INSERT INTO compteur_config (type_compteur, label, actif, ordre) "
        "VALUES ('eau_general', '💧 Compteur EAU Général', 1, 0)"
    )


def downgrade():
    op.drop_index("ix_compteur_config_type_compteur", "compteur_config")
    op.drop_table("compteur_config")
