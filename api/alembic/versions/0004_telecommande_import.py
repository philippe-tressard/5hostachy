"""Ajout colonne chez_locataire sur telecommande + table telecommande_import

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── 1. Colonne chez_locataire sur la table existante telecommande ──────
    cols_tc = [c["name"] for c in inspector.get_columns("telecommande")]
    if "chez_locataire" not in cols_tc:
        op.add_column(
            "telecommande",
            sa.Column("chez_locataire", sa.Boolean(), nullable=False, server_default="0"),
        )

    # ── 2. Table telecommande_import ────────────────────────────────────────
    tables = inspector.get_table_names()
    if "telecommande_import" not in tables:
        op.create_table(
            "telecommande_import",
            sa.Column("id",                    sa.Integer(),  primary_key=True, autoincrement=True),
            sa.Column("nom_proprietaire",      sa.String(),   nullable=False),
            sa.Column("nom_locataire",         sa.String(),   nullable=True),
            sa.Column("reference",             sa.String(),   nullable=True),
            sa.Column("statut",                sa.String(),   nullable=False, server_default="en_attente"),
            sa.Column("user_proprietaire_id",  sa.Integer(),  sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("user_locataire_id",     sa.Integer(),  sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("lot_id",                sa.Integer(),  sa.ForeignKey("lot.id"),          nullable=True),
            sa.Column("chez_locataire",        sa.Boolean(),  nullable=False, server_default="0"),
            sa.Column("refuse_par_locataire",  sa.Boolean(),  nullable=False, server_default="0"),
            sa.Column("telecommande_id",       sa.Integer(),  sa.ForeignKey("telecommande.id"), nullable=True),
            sa.Column("notes_admin",           sa.Text(),     nullable=True),
            sa.Column("importe_le",            sa.DateTime(), nullable=False),
            sa.Column("resolu_le",             sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("telecommande_import")
    op.drop_column("telecommande", "chez_locataire")
