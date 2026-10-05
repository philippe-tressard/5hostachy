"""La fusion d'affaires à la clôture : l'affaire absorbée nomme sa principale (#1704)

Arbitré le 05/10/2026 : clore une affaire peut absorber ses affaires liées
encore ouvertes. Leurs Suites, messages, documents et courriels rejoignent
l'affaire qu'on clôt ; elles-mêmes sont closes en même temps et portent
`ticket.fusionnee_dans_id` — ce qui les retire du carnet et des moyennes, et
renvoie leur fiche vers la principale (`utils/fusion_affaires`).

Colonne simple, nullable, SANS clé étrangère : un `add_column` ne doit jamais
en porter (0117, 0165).

Idempotente : la colonne n'est posée que si elle manque.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0265
Revises: 0264
"""

import sqlalchemy as sa

from alembic import op

revision = "0265"
down_revision = "0264"
branch_labels = None
depends_on = None

TABLE = "ticket"  # identifiants : constantes du fichier
COLONNE = "fusionnee_dans_id"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    if COLONNE not in _colonnes(op.get_bind()):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer, nullable=True))


def downgrade():
    if COLONNE in _colonnes(op.get_bind()):
        with op.batch_alter_table(TABLE) as batch:
            batch.drop_column(COLONNE)
