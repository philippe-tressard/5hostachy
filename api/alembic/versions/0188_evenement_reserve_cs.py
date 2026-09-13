"""`evenement.reserve_cs` : un événement peut se préparer à l'abri du conseil syndical.

## Pourquoi (13/09/2026, #939)

Arbitrage de l'utilisateur, après analyse des quatre options de publication sur un
événement :

> « Oui pour la visibilité CS, laisse les deux autres. »

C'était le seul manque réel. Un événement était **tout ou rien** : visible de
tous, ou inexistant. Préparer une assemblée générale, noter une visite de
contrôle avant d'en informer les résidents — rien ne permettait de le faire dans
l'outil, et le conseil syndical le faisait donc ailleurs.

🔴 **Les deux autres options ne sont PAS livrées, et c'est une décision** :

* 🚨 *Marquer urgent* — un événement porte une DATE, et c'est elle qui dit
  l'urgence. Deux signaux qui se contredisent (« dans trois mois » / « urgent »)
  valent moins qu'un seul.
* 🔒 *Rendre confidentiel* — la lecture d'un événement suit déjà son périmètre
  (`evenement_visible`). Il n'y aurait **rien à restreindre** de plus, et une
  case sans effet observable est pire qu'une case absente.

## Le nom de la colonne

`reserve_cs`, et non `brouillon` (Publication) ni `confidentiel` (Ticket). Ces
deux-là sont **historiques** — deux noms pour une notion, et le dépôt le
documente comme une dette (`$lib/options-publication`). Un troisième nom
historique aurait aggravé ; celui-ci dit ce que la colonne fait.

⚠️ Côté écran, les trois se rendent par la MÊME case (clé `brouillon` de la table
des options) : c'est le pont dans le front qui relie, exactement comme pour le
ticket. Une seule case, un seul libellé, trois colonnes — l'inverse aurait été
trois cases pour une notion.

## Valeur par défaut

`0` — aucun événement existant ne devient invisible. Une migration qui masquerait
du contenu déjà publié serait une perte de données du point de vue de qui le
lisait hier.
"""
import sqlalchemy as sa
from alembic import op

revision = "0188"
down_revision = "0187"
branch_labels = None
depends_on = None

TABLE = "evenement"
COLONNE = "reserve_cs"


def _colonnes() -> set[str]:
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(TABLE)}


def upgrade() -> None:
    #  Garde d'idempotence : un redémarrage qui rejoue la migration ne doit pas
    #  échouer sur une colonne déjà posée. `start.sh` a `set -e` — une migration
    #  qui crashe laisse le conteneur bloqué.
    if COLONNE not in _colonnes():
        op.add_column(
            TABLE,
            sa.Column(COLONNE, sa.Boolean(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    if COLONNE in _colonnes():
        op.drop_column(TABLE, COLONNE)
