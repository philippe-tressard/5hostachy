"""Create delegation table + add aidant statut

Revision ID: 0077
Revises: 0076
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delegation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("mandant_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("aidant_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("statut", sa.String(), nullable=False, server_default="en_attente"),
        sa.Column("motif", sa.String(), nullable=False, server_default=""),
        sa.Column("date_debut", sa.Date(), nullable=False),
        sa.Column("date_fin", sa.Date(), nullable=True),
        sa.Column("cree_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("revoque_le", sa.DateTime(), nullable=True),
        sa.Column("revoque_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
    )
    # Index pour retrouver rapidement les délégations actives d'un aidant
    op.create_index("ix_delegation_aidant_statut", "delegation", ["aidant_id", "statut"])
    op.create_index("ix_delegation_mandant_statut", "delegation", ["mandant_id", "statut"])


def downgrade() -> None:
    op.drop_index("ix_delegation_mandant_statut", "delegation")
    op.drop_index("ix_delegation_aidant_statut", "delegation")
    op.drop_table("delegation")
