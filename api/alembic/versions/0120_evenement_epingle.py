"""Épinglage d'un événement, sur le modèle des publications.

Même nom de champ que `publication.epingle` : le fil et les badges lisent déjà
cette notion, il n'y a pas de raison d'en inventer une seconde.

Idempotente (cf. 0117-0119) : la colonne n'est ajoutée que si elle manque.

Revision ID: 0120
Revises: 0119
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0120"
down_revision = "0119"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if "epingle" not in _colonnes("evenement"):
        op.add_column(
            "evenement",
            sa.Column("epingle", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )


def downgrade():
    op.drop_column("evenement", "epingle")
