"""ticket: champs saisi_pour (user_id, nom, email)

Revision ID: 0100
Revises: 0099
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '0100'
down_revision = '0099'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('ticket') as batch_op:
        batch_op.add_column(sa.Column('saisi_pour_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('saisi_pour_nom', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('saisi_pour_email', sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('ticket') as batch_op:
        batch_op.drop_column('saisi_pour_email')
        batch_op.drop_column('saisi_pour_nom')
        batch_op.drop_column('saisi_pour_user_id')
