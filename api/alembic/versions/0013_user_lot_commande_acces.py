"""Créer tables user_lot et commande_acces (manquantes dans les migrations précédentes)

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "user_lot" not in tables:
        op.create_table(
            "user_lot",
            sa.Column("id",          sa.Integer(),  primary_key=True, autoincrement=True),
            sa.Column("user_id",     sa.Integer(),  sa.ForeignKey("utilisateur.id"), nullable=False),
            sa.Column("lot_id",      sa.Integer(),  sa.ForeignKey("lot.id"),         nullable=False),
            sa.Column("type_lien",   sa.String(),   nullable=False, server_default="propriétaire"),
            sa.Column("quote_part",  sa.Float(),    nullable=True),
            sa.Column("actif",       sa.Boolean(),  nullable=False, server_default="1"),
        )

    if "commande_acces" not in tables:
        op.create_table(
            "commande_acces",
            sa.Column("id",             sa.Integer(),  primary_key=True, autoincrement=True),
            sa.Column("user_id",        sa.Integer(),  sa.ForeignKey("utilisateur.id"), nullable=False),
            sa.Column("lot_id",         sa.Integer(),  sa.ForeignKey("lot.id"),         nullable=False),
            sa.Column("type",           sa.String(),   nullable=False),
            sa.Column("quantite",       sa.Integer(),  nullable=False, server_default="1"),
            sa.Column("motif",          sa.String(),   nullable=True),
            sa.Column("statut",         sa.String(),   nullable=False, server_default="en_attente"),
            sa.Column("traite_par_id",  sa.Integer(),  sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("motif_refus",    sa.String(),   nullable=True),
            sa.Column("cree_le",        sa.DateTime(), nullable=False),
            sa.Column("traite_le",      sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("commande_acces")
    op.drop_table("user_lot")
