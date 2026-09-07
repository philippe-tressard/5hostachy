"""TypeEquipement : ajout des valeurs 'eau' et 'pompe'

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-10
"""
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite stocke les enums en VARCHAR : aucune modification de schéma nécessaire.
    # La migration documente l'ajout des nouvelles valeurs 'eau' et 'pompe'.
    pass


def downgrade():
    pass
