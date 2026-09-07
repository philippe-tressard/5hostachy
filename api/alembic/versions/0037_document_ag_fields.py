"""0037 — Document : champs AG (annee, date_ag, batiments_ids_json)"""

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column('document', sa.Column('annee', sa.Integer(), nullable=True))
    op.add_column('document', sa.Column('date_ag', sa.Date(), nullable=True))
    op.add_column('document', sa.Column('batiments_ids_json', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('document', 'batiments_ids_json')
    op.drop_column('document', 'date_ag')
    op.drop_column('document', 'annee')
