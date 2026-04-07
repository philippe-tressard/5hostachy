"""ConfigSite : whatsapp_community_url

Revision ID: 0086
Revises: 0085
Create Date: 2026-04-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT OR IGNORE INTO config_site (cle, valeur) VALUES (:cle, :val)"
        ).bindparams(
            cle="whatsapp_community_url",
            val="https://chat.whatsapp.com/FyBjmFwTH5eA5BJcXkmjFj",
        )
    )


def downgrade() -> None:
    op.execute("DELETE FROM config_site WHERE cle = 'whatsapp_community_url'")
