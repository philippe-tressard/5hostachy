"""SyndicInfo : ajout champ site_web

Revision ID: 0085
Revises: 0084
Create Date: 2026-04-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = [row[1] for row in conn.execute(sa.text("PRAGMA table_info('syndic_info')"))]
    if "site_web" not in columns:
        op.add_column("syndic_info", sa.Column("site_web", sa.Text, nullable=True))
    # Seed valeur IFF Gestion
    op.execute(
        sa.text("UPDATE syndic_info SET site_web = :url WHERE site_web IS NULL").bindparams(
            url="https://extranet.immoscope.fr/extranet?P1=SUZG"
        )
    )


def downgrade() -> None:
    op.drop_column("syndic_info", "site_web")
