"""document: ajout publication_id (pièces jointes publications)

Revision ID: 0101
Revises: 0100
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = '0101'
down_revision = '0100'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('document') as batch_op:
        batch_op.add_column(sa.Column('publication_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('document') as batch_op:
        batch_op.drop_column('publication_id')
