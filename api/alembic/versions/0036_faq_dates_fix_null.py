"""0036 — FAQ : corriger les lignes avec cree_le / mis_a_jour_le IS NULL"""

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import text


def upgrade() -> None:
    op.execute(text("UPDATE faq_item SET cree_le = datetime('now') WHERE cree_le IS NULL"))
    op.execute(text("UPDATE faq_item SET mis_a_jour_le = datetime('now') WHERE mis_a_jour_le IS NULL"))


def downgrade() -> None:
    pass
