"""0034 — FAQ : corriger les lignes avec actif IS NULL (colonne NOT NULL sans DEFAULT SQL)"""

revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import text


def upgrade() -> None:
    op.execute(text("UPDATE faq_item SET actif = 1 WHERE actif IS NULL"))


def downgrade() -> None:
    pass
