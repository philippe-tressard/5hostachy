"""Ajout photo_url sur copropriete et image_url sur publication

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cols_copropriete = [c["name"] for c in inspector.get_columns("copropriete")]
    if "photo_url" not in cols_copropriete:
        op.add_column("copropriete", sa.Column("photo_url", sa.String(), nullable=True))

    cols_publication = [c["name"] for c in inspector.get_columns("publication")]
    if "image_url" not in cols_publication:
        op.add_column("publication", sa.Column("image_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("publication", "image_url")
    op.drop_column("copropriete", "photo_url")
