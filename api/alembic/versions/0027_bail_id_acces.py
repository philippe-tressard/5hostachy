"""Ajout bail_id sur vigik et telecommande pour traçabilité des transferts locataire.

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('vigik') as batch_op:
        if not _col_exists('vigik', 'chez_locataire'):
            batch_op.add_column(sa.Column('chez_locataire', sa.Boolean(), nullable=False, server_default='0'))
        if not _col_exists('vigik', 'bail_id'):
            batch_op.add_column(sa.Column('bail_id', sa.Integer(), nullable=True))

    with op.batch_alter_table('telecommande') as batch_op:
        if not _col_exists('telecommande', 'bail_id'):
            batch_op.add_column(sa.Column('bail_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('vigik') as batch_op:
        batch_op.drop_column('bail_id')
    with op.batch_alter_table('telecommande') as batch_op:
        batch_op.drop_column('bail_id')


def _col_exists(table: str, col: str) -> bool:
    from alembic import op as _op
    bind = _op.get_bind()
    insp = sa.inspect(bind)
    return any(c['name'] == col for c in insp.get_columns(table))
