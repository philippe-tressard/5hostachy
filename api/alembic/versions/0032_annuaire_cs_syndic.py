"""0032 — Annuaire CS & Syndic : tables dédiées indépendantes des comptes"""

revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        'ag_cs_info',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('ag_annee', sa.Integer, nullable=True),
        sa.Column('ag_date', sa.Date, nullable=True),
    )

    op.create_table(
        'membre_cs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('genre', sa.String, nullable=False),          # Mr / Mme / Mlle
        sa.Column('prenom', sa.String, nullable=False),
        sa.Column('nom', sa.String, nullable=False),
        sa.Column('batiment_id', sa.Integer, sa.ForeignKey('batiment.id'), nullable=True),
        sa.Column('etage', sa.Integer, nullable=True),
        sa.Column('ordre', sa.Integer, nullable=False, server_default='0'),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('utilisateur.id'), nullable=True),
    )

    op.create_table(
        'syndic_info',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('nom_syndic', sa.String, nullable=False, server_default=''),
        sa.Column('adresse', sa.String, nullable=False, server_default=''),
    )

    op.create_table(
        'membre_syndic',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('genre', sa.String, nullable=False),          # Mr / Mme / Mlle
        sa.Column('prenom', sa.String, nullable=False),
        sa.Column('nom', sa.String, nullable=False),
        sa.Column('fonction', sa.String, nullable=True),
        sa.Column('email', sa.String, nullable=True),
        sa.Column('telephone', sa.String, nullable=True),       # CSV, même pattern que Prestataire
        sa.Column('est_principal', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('ordre', sa.Integer, nullable=False, server_default='0'),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('utilisateur.id'), nullable=True),
    )


def downgrade():
    op.drop_table('membre_syndic')
    op.drop_table('syndic_info')
    op.drop_table('membre_cs')
    op.drop_table('ag_cs_info')
