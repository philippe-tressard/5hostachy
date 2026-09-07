"""Ajout champs destinataire_cs (ticket) et envoyer_cs (publication).

Revision ID: 0097
Revises: 0096
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ticket",
        sa.Column("destinataire_cs", sa.Boolean, nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "publication",
        sa.Column("envoyer_cs", sa.Boolean, nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("publication", "envoyer_cs")
    op.drop_column("ticket", "destinataire_cs")
