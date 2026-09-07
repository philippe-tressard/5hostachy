"""Table lot_import (staging lots depuis Excel)

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "lot_import" not in tables:
        op.create_table(
            "lot_import",
            sa.Column("id",                  sa.Integer(),  primary_key=True, autoincrement=True),
            sa.Column("batiment_id",         sa.Integer(),  sa.ForeignKey("batiment.id"), nullable=True),
            sa.Column("numero",              sa.String(),   nullable=False),
            sa.Column("type_raw",            sa.String(),   nullable=False),
            sa.Column("etage_raw",           sa.String(),   nullable=True),
            sa.Column("no_coproprietaire",   sa.String(),   nullable=True),
            sa.Column("nom_coproprietaire",  sa.String(),   nullable=True),
            sa.Column("statut",              sa.String(),   nullable=False, server_default="en_attente"),
            sa.Column("lot_id",              sa.Integer(),  sa.ForeignKey("lot.id"),         nullable=True),
            # JSON array : [{"user_id": N, "type_lien": "propriétaire"/"locataire"}, ...]
            sa.Column("utilisateurs_json",   sa.String(),   nullable=False, server_default="[]"),
            sa.Column("notes_admin",         sa.Text(),     nullable=True),
            sa.Column("importe_le",          sa.DateTime(), nullable=False),
            sa.Column("resolu_le",           sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("lot_import")
