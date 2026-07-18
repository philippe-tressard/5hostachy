"""Ajout cree_le sur prestataire, membre_cs, membre_syndic (pour le fil d'actualité).

Revision ID: 0113
Revises: 0112
Create Date: 2026-07-18

Ces tables n'avaient aucun horodatage. Le fil d'actualité en a besoin pour dater
les nouvelles fiches. On backfille les lignes existantes à une date ancienne
(2020-01-01) — antérieure à la fenêtre du fil (~377 j) — pour qu'elles ne
remontent PAS rétroactivement au fil. Les nouvelles lignes prennent datetime.utcnow
via le modèle SQLModel.
"""
import sqlalchemy as sa
from alembic import op

revision = "0113"
down_revision = "0112"
branch_labels = None
depends_on = None

_BACKFILL = "2020-01-01 00:00:00"
_TABLES = ("prestataire", "membre_cs", "membre_syndic")


def upgrade():
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("cree_le", sa.DateTime(), nullable=False,
                      server_default=_BACKFILL),
        )


def downgrade():
    for table in _TABLES:
        op.drop_column(table, "cree_le")
