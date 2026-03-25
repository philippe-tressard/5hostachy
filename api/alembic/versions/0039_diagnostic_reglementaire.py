"""0039 — Diagnostics et contrôles réglementaires (types + rapports)"""

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.create_table(
        'diagnostic_type',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('code', sa.String(), nullable=False, unique=True),
        sa.Column('nom', sa.String(), nullable=False),
        sa.Column('texte_legislatif', sa.Text(), nullable=False),
        sa.Column('frequence', sa.String(), nullable=True),
        sa.Column('ordre', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('actif', sa.Boolean(), nullable=False, server_default='1'),
    )
    op.create_table(
        'diagnostic_rapport',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('diagnostic_type_id', sa.Integer(), sa.ForeignKey('diagnostic_type.id'), nullable=False),
        sa.Column('titre', sa.String(), nullable=False),
        sa.Column('date_rapport', sa.Date(), nullable=True),
        sa.Column('fichier_nom', sa.String(), nullable=False),
        sa.Column('fichier_chemin', sa.String(), nullable=False),
        sa.Column('taille_octets', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(), nullable=False, server_default='application/octet-stream'),
        sa.Column('publie_par_id', sa.Integer(), sa.ForeignKey('utilisateur.id'), nullable=False),
        sa.Column('publie_le', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('diagnostic_rapport')
    op.drop_table('diagnostic_type')
