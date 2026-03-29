"""Create regle_residence table

Revision ID: 0076
Revises: 0075
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regle_residence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("titre", sa.String(), nullable=False),
        sa.Column("contenu", sa.String(), nullable=False, server_default=""),
        sa.Column("ordre", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cree_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("modifie_le", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("regle_residence")
