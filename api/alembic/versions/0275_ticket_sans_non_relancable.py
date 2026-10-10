"""Les colonnes mortes `ticket.non_relancable` et son motif sont retirées (#1797)

Second temps de la contraction (règle #1757, `test_migrations_compatibles.py`).
Le premier, v2.130.5, a retiré les deux champs du code ; la 0272 a donné à
`non_relancable` le défaut sans lequel une création d'affaire aurait échoué.
Plus rien ne les lit ni ne les écrit : la relance syndic propose toute affaire
suivie depuis v2.130.2 (#1796). Revenir à v2.130.5 ne demande donc pas de
restaurer la base — ce code-là ne les déclare déjà plus.

## Comment elles partent

`op.drop_column`, un retrait en place, natif sous PostgreSQL comme sous SQLite ≥ 3.35 —
et PAS le mode `batch` d'Alembic, qui recopierait `ticket`, cible de clés
étrangères de toute l'application (même choix que la 0250). Aucune des deux
colonnes n'est indexée, clé ou contrainte.

Idempotente : `start.sh` a `set -e`, et un redémarrage après une migration
interrompue la rejoue. Colonne déjà absente → rien à faire. `downgrade` les
rétablit (`non_relancable` à `false` partout, le motif vide) : les valeurs
d'origine ne reviennent pas, et aucun code ne les lit.

⚠️ Le nom de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0275
Revises: 0274
"""

import sqlalchemy as sa

from alembic import op

revision = "0275"
down_revision = "0274"
branch_labels = None
depends_on = None

TABLE = "ticket"  # identifiants : constantes du fichier
DRAPEAU = "non_relancable"
MOTIF = "non_relancable_motif"


def _colonnes() -> set[str]:
    conn = op.get_bind()
    if TABLE not in sa.inspect(conn).get_table_names():
        return set()
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade() -> None:
    presentes = _colonnes()
    if DRAPEAU in presentes:
        op.drop_column(TABLE, DRAPEAU)
    if MOTIF in presentes:
        op.drop_column(TABLE, MOTIF)


def downgrade() -> None:
    presentes = _colonnes()
    if not presentes:
        return
    if DRAPEAU not in presentes:
        op.add_column(
            TABLE,
            sa.Column(DRAPEAU, sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if MOTIF not in presentes:
        op.add_column(TABLE, sa.Column(MOTIF, sa.Text(), nullable=True))
