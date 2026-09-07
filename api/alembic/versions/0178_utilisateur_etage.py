"""L'étage d'un résident — facultatif, demandé à l'inscription (#821).

Demandé le 07/09/2026 : *« il serait aussi intéressant de réclamer l'étage (en
non obligatoire) d'un nouvel utilisateur qui s'inscrit »*.

## Pourquoi sur l'utilisateur et pas sur le lot

`Lot` porte déjà un `etage`. Mais un compte n'est rattaché à un lot qu'APRÈS
validation et rapprochement automatique — souvent des jours plus tard, parfois
jamais quand l'import ne l'a pas trouvé (cf. l'audit des baux sans locataire).
Or l'étage sert dès l'inscription : il situe la personne pour l'annonce
d'arrivée, et il aide le conseil à savoir de qui il parle.

⚠️ Les deux ne font pas double emploi et ne doivent pas être fondus : celui du
lot décrit **un bien**, celui-ci décrit **où quelqu'un habite**. Un bailleur a
un lot au 4ᵉ et habite ailleurs.

## Facultatif, et ce n'est pas un détail

L'étage est une donnée plus précise que le bâtiment : couplé à lui, il approche
l'identification du logement. Il reste donc **facultatif** à la saisie, et il
n'apparaît dans l'annonce d'arrivée **que s'il a été renseigné**. Personne n'a
à le donner pour se créer un compte.

Revision ID: 0178
Revises: 0177
"""
import sqlalchemy as sa
from alembic import op

revision = "0178"
down_revision = "0177"
branch_labels = None
depends_on = None

TABLE = "utilisateur"
COLONNE = "etage"


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    #  Idempotente : `start.sh` a `set -e`, et une migration qui rejoue sur une
    #  colonne déjà posée bloquerait le conteneur au démarrage. C'est arrivé deux
    #  fois (0117 le 25/07/2026, 0165 le 01/09) sans que personne le voie.
    #
    #  ⚠️ Colonne SIMPLE, sans `ForeignKey` : SQLite refuse d'altérer les
    #  contraintes d'une table existante (`CLAUDE.md`). Ici la question ne se
    #  pose pas — un étage est un entier — mais la règle vaut d'être rappelée à
    #  chaque `add_column`.
    if COLONNE not in _colonnes(TABLE):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE, COLONNE)
