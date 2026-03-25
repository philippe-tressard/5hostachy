"""Config site — table clé/valeur pour persistance multi-appareils des paramètres admin.

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'config_site',
        sa.Column('cle', sa.String(), primary_key=True),
        sa.Column('valeur', sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table('config_site')
