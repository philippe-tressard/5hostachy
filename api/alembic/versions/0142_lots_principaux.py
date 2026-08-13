"""La fiche copropriété distingue enfin les deux décomptes de lots du registre ANAH.

La fiche du registre national d'immatriculation en porte **deux**, et ils ne
disent pas la même chose :

  - *Nombre de lots* — tous les lots, caves et parkings compris ;
  - *Nombre de lots à usage d'habitation, de commerces et de bureaux* — celui qui
    porte les seuils réglementaires, et qui répond à « combien de foyers ici ».

Relevé réel sur la résidence : **195** et **63**. L'application n'avait qu'un
champ, `nb_lots_total`, si bien qu'il fallait choisir lequel des deux perdre — et
que le chiffre saisi ne disait pas lequel il était. Selon la réponse, le produit
annonçait une taille de copropriété fausse du simple au triple.

**Colonne nullable, sans valeur par défaut, et aucun rétro-remplissage.** On ne
peut pas déduire les lots principaux du total : le rapport dépend du nombre de
caves et de parkings, propre à chaque copropriété. Déduire « 63 » d'un « 195 »
par une règle de trois inventerait une mesure — la faute que `standards/04` et
la migration 0137 avant celle-ci interdisent explicitement. Le champ reste vide
jusqu'à ce qu'un administrateur le renseigne, et l'écran affiche alors le seul
chiffre qu'il a.

Revision ID: 0142
Revises: 0141
Create Date: 2026-08-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0142"
down_revision = "0141"
branch_labels = None
depends_on = None

TABLE = "copropriete"
COLONNE = "nb_lots_principaux"


def _colonnes(table: str) -> set:
    """Colonnes réellement présentes, lues sur la base en cours de migration.

    Même précaution qu'en 0137 : ajouter une colonne déjà présente ferait échouer
    `alembic upgrade`, et `start.sh` a `set -e` — le conteneur ne démarrerait
    plus, sur les deux nœuds.
    """
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(table)}


def upgrade() -> None:
    if COLONNE in _colonnes(TABLE):
        return
    op.add_column(TABLE, sa.Column(COLONNE, sa.Integer(), nullable=True))


def downgrade() -> None:
    if COLONNE not in _colonnes(TABLE):
        return
    op.drop_column(TABLE, COLONNE)
