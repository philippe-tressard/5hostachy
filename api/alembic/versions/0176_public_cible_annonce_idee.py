"""Le public cible d'une annonce et d'une idée — la section 5 du cadre.

Demandé le 06/09/2026 : *« sur boîtes à idées et annonces, ajoute la section
Destinataires ; en nouveau et en édition »* (#782).

## 🔴 Ce que cette migration renverse

Les deux entités déclaraient cette section **sans objet**, avec un raisonnement
écrit noir sur blanc dans `front/src/lib/entites/` :

* l'annonce — « c'est la rubrique qui filtre qui y entre, pas l'annonce. On
  n'annonce pas un lave-linge à trois voisins choisis » ;
* l'idée — « restreindre qui peut la lire la priverait des voix qui la portent ».

Ces raisonnements n'étaient pas absurdes ; ils ont été **tranchés autrement**, et
c'est la deuxième fois que l'écran réfute le papier sur la petite annonce (la
première : le workflow, absent puis ajouté le 18/08/2026, migration 0151). La
déclaration a rendu le désaccord visible en un seul endroit — c'est ce à quoi
elle sert.

Philippe a choisi la lecture **forte** : le public cible filtre la **visibilité**,
comme pour le sondage — pas seulement les notifications.

## La MÊME forme que partout ailleurs

Du JSON de codes (`["copropriétaires","locataires"]`), lu par
`public_cible_visible` et par `$lib/destinataires.ts`, qui ne savent lire que
celle-là. `Publication.public_cible` et `Sondage.public_cible` portent déjà le
même champ, sous le même nom. **Ne pas inventer une troisième forme** : c'est ce
que le sondage avait fait avec `profils_autorises`, et il a fallu une migration
pour l'en sortir (#316).

## Les lignes existantes — le cas zéro, et il est décisif

`NULL` sur toutes les annonces et idées déjà déposées. C'est délibéré, et pas un
oubli : `public_cible_visible` traite l'absence comme **« tout le monde »**, ce
que le produit leur appliquait de fait. Un `server_default` aurait figé une liste
qui n'a jamais été choisie par personne.

⚠️ L'inverse — absence lue comme « visible de personne » — aurait rendu invisibles
d'un seul coup toutes les annonces et toutes les idées de la copropriété, sans
message d'erreur ni ligne de journal. C'est la forme de panne la plus difficile à
diagnostiquer : rien ne casse, tout disparaît.

Revision ID: 0176
Revises: 0175
"""
import sqlalchemy as sa
from alembic import op

revision = "0176"
down_revision = "0175"
branch_labels = None
depends_on = None

COLONNE = "public_cible"
TABLES = ("petite_annonce", "idee")


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    #  Idempotente : `start.sh` a `set -e`, et une migration qui rejoue sur une
    #  colonne déjà posée bloquerait le conteneur au démarrage. C'est arrivé deux
    #  fois (0117 le 25/07/2026, 0165 le 01/09) sans que personne le voie.
    for table in TABLES:
        if COLONNE not in _colonnes(table):
            op.add_column(table, sa.Column(COLONNE, sa.String(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, COLONNE)
