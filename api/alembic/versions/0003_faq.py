"""Création de la table faq_item

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "faq_item" not in inspector.get_table_names():
        op.create_table(
            "faq_item",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("categorie", sa.String(), nullable=False, default=""),
            sa.Column("question", sa.String(), nullable=False),
            sa.Column("reponse", sa.Text(), nullable=False),
            sa.Column("ordre", sa.Integer(), nullable=False, default=0),
            sa.Column("actif", sa.Boolean(), nullable=False, default=True),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
            sa.Column("mis_a_jour_le", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("faq_item")
