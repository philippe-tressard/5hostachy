"""publication : état « publié » par défaut + migration des publications sans état

Révision ID: 0111
Revises: 0110
Create Date: 2026-06-15

Ajout de l'état « publié » (défaut, hors workflow). Les publications existantes
sans état (statut NULL) deviennent « publié ». Combiné à la règle de visibilité
1 mois côté router (_is_archived), celles publiées depuis plus de 30 jours
basculeront automatiquement dans l'Historique.
"""
from alembic import op
from sqlalchemy import text

revision = '0111'
down_revision = '0110'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(text("UPDATE publication SET statut = 'publie' WHERE statut IS NULL"))


def downgrade():
    op.execute(text("UPDATE publication SET statut = NULL WHERE statut = 'publie'"))
