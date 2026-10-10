"""Le suivi d'une actualité : ouvert, résolu ou annulé — optionnel, posé par le conseil

Arbitré le 10/10/2026 : une affaire de catégorie « Actualité » peut porter un
suivi à trois états, que seul le conseil syndical active. C'est un REPÈRE : il
ne fait entrer l'actualité ni au kanban, ni aux relances, ni aux compteurs —
d'où une colonne à part, `statut` restant `publie` (`utils/suivi_actualite`).

Colonne simple, nullable, sans défaut : `NULL` = sans suivi, ce que sont toutes
les actualités existantes. Ajouter seulement — rien n'est retiré ni renommé, la
version précédente du code l'ignore (#1757).

Idempotente : la colonne n'est posée que si elle manque.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0272
Revises: 0271
"""

import sqlalchemy as sa

from alembic import op

revision = "0272"
down_revision = "0271"
branch_labels = None
depends_on = None

TABLE = "ticket"  # identifiants : constantes du fichier
COLONNE = "suivi_actualite"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    if COLONNE not in _colonnes(op.get_bind()):
        op.add_column(TABLE, sa.Column(COLONNE, sa.String, nullable=True))


def downgrade():
    if COLONNE in _colonnes(op.get_bind()):
        with op.batch_alter_table(TABLE) as batch:
            batch.drop_column(COLONNE)
