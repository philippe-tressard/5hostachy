"""sondage : champ_libre sur option, reponse_libre sur vote

Revision ID: 0073
Revises: 0072
"""
from alembic import op
import sqlalchemy as sa

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("option_sondage", sa.Column("champ_libre", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("vote_sondage", sa.Column("reponse_libre", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("vote_sondage", "reponse_libre")
    op.drop_column("option_sondage", "champ_libre")
