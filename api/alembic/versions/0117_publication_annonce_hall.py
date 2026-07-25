"""Annonce de hall générée depuis une actualité.

- `publication.annonce_hall` : option de publication (comme partager_whatsapp / envoyer_cs)
- `annonce_hall.publication_id` : traçabilité de l'actualité d'origine

Revision ID: 0117
Revises: 0116
Create Date: 2026-07-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0117"
down_revision = "0116"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "publication",
        sa.Column("annonce_hall", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "annonce_hall",
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publication.id"), nullable=True),
    )


def downgrade():
    op.drop_column("annonce_hall", "publication_id")
    op.drop_column("publication", "annonce_hall")
