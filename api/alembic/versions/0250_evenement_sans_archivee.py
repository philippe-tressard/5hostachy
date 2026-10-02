"""La colonne morte `evenement.archivee` est retirée (#1568, 02/10/2026)

L'archivage des événements est parti avec leur passage en affaires (#1092,
migration 0212) : un événement du calendrier est désormais une affaire, archivée
par la règle « ticket » ou « actualite » de `utils/archivage.REGLES`. La colonne
`evenement.archivee` (0049) n'était plus lue ni écrite par personne — et une
colonne que plus rien n'écrit est une seconde façon de disparaître qui n'attend
que d'être de nouveau utilisée. Le test de `test_archivage.py` refuse désormais
tout booléen de disparition non déclaré.

La TABLE `evenement` reste : elle est lue (visibilité des documents, comptage du
patrimoine).

## Comment la colonne part

`ALTER TABLE … DROP COLUMN`, natif depuis SQLite 3.35 (l'image `python:3.12-slim`
embarque 3.40 ou plus) — et PAS le mode `batch` d'Alembic, qui recopie la table :
`evenement` est la cible de clés étrangères (`evenement_evolution`, `document`),
et supprimer puis renommer une table parente sous `PRAGMA foreign_keys=ON` est
exactement ce qu'on évite sur la base de production. La colonne n'est ni
indexée, ni clé, ni contrainte : SQLite accepte de la retirer en place.

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue. Colonne déjà absente (ou table absente) → rien à faire.
`downgrade` la rétablit à l'identique de la 0049 (`NOT NULL`, défaut 0) ; les
valeurs d'origine ne reviennent pas (toutes les lignes reprennent le défaut).

⚠️ Le nom de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0250
Revises: 0249
"""

import sqlalchemy as sa
from alembic import op

revision = "0250"
down_revision = "0249"
branch_labels = None
depends_on = None

TABLE = "evenement"
COLONNE = "archivee"


def _colonnes() -> set[str]:
    conn = op.get_bind()
    if TABLE not in sa.inspect(conn).get_table_names():
        return set()
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade() -> None:
    if COLONNE in _colonnes():
        op.drop_column(TABLE, COLONNE)


def downgrade() -> None:
    presentes = _colonnes()
    if presentes and COLONNE not in presentes:
        op.add_column(
            TABLE, sa.Column(COLONNE, sa.Boolean(), nullable=False, server_default="0")
        )
