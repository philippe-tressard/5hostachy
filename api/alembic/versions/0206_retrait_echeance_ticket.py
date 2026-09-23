"""L'échéance d'une affaire n'existe plus (#1092).

## L'arbitrage, pris le 23/09/2026

> « La colonne `echeance` des affaires n'est plus saisie depuis le 21/09 et
>   personne ne la lit. On la retire ? » — **La retirer.**

Ôtée du formulaire le 21/09/2026 sur arbitrage — *« il y a un mécanisme
automatique de relance d'une affaire non résolue chaque mois »* —, elle restait
en base : écrite par la création, relue par personne. C'est le défaut que la
0205 décrit pour `visible_jusqu_au`, et qu'elle citait déjà en exemple.

## Vérifié avant d'écrire cette migration

La sauvegarde du 23/09/2026 à 02:00, lue dans un conteneur jetable, sans ouvrir
la base vivante : **0 échéance renseignée sur 36 affaires**. Rien n'est perdu.
`downgrade` remet la colonne, vide.
"""
import sqlalchemy as sa
from alembic import op

revision = "0206"
down_revision = "0205"
branch_labels = None
depends_on = None

#: L'identifiant ne peut pas se lier en SQLite : il vient de cette constante.
TABLE = "ticket"
COLONNE = "echeance"


def _colonnes_existantes(conn, table: str) -> set[str]:
    """L'inspecteur plutôt qu'un `PRAGMA` en f-string (cf. 0204)."""
    return {colonne["name"] for colonne in sa.inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    if COLONNE not in _colonnes_existantes(conn, TABLE):
        return
    with op.batch_alter_table(TABLE) as lot:
        lot.drop_column(COLONNE)


def downgrade():
    op.add_column(TABLE, sa.Column(COLONNE, sa.Date(), nullable=True))
