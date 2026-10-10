"""`ticket.non_relancable` reçoit un défaut : le code cesse de la déclarer (#1797)

Premier temps d'une contraction (règle #1757, `test_migrations_compatibles.py`).
Depuis v2.130.2 (#1796), la relance syndic ne lit plus la colonne ; ce lot retire
aussi le champ du modèle, des schémas, des routeurs et du client. La colonne,
elle, reste jusqu'à une version ULTÉRIEURE — sans quoi revenir à l'image
précédente demanderait de restaurer la base.

## Pourquoi un défaut

Le modèle cessant de la déclarer, l'application insère des affaires SANS cette
colonne. Elle est `NOT NULL` :
- une base migrée par la 0104 porte `server_default="0"` — rien à faire ;
- une base née du schéma courant (`utils/schema_initial`, `create_all`) n'en
  porte AUCUN : c'est le cas de la production depuis le passage sous PostgreSQL,
  et toute création d'affaire y échouerait.

La migration pose donc le défaut là où il manque, et seulement là. Sous SQLite,
`batch_alter_table` recrée la table : réservé aux bases qui en ont besoin.
`non_relancable_motif` est nullable, elle n'a besoin de rien.

Idempotente : rejouée, elle trouve le défaut posé.

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
COLONNE = "non_relancable"


def _colonne(conn) -> dict | None:
    for c in sa.inspect(conn).get_columns(TABLE):
        if c["name"] == COLONNE:
            return c
    return None


def upgrade():
    colonne = _colonne(op.get_bind())
    if colonne is None or colonne.get("default") is not None:
        return
    with op.batch_alter_table(TABLE) as batch:
        batch.alter_column(
            COLONNE,
            existing_type=sa.Boolean(),
            existing_nullable=colonne["nullable"],
            server_default=sa.false(),
        )


def downgrade():
    #  Rien à défaire : un défaut ne gêne aucune version du code, et la version
    #  précédente écrit la colonne elle-même.
    pass
