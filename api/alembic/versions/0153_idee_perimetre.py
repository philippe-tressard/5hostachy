"""Le périmètre d'une idée — troisième entité de la Communauté à le recevoir.

Demandé le 18/08/2026 : *« Boîte à idées […] ajouter la section périmètre »*.

## Pourquoi une idée a un périmètre

Le même raisonnement que pour la petite annonce (migration 0151), et il s'était
déjà révélé juste une fois : la copropriété compte quatre bâtiments, un parking,
des caves et une AFUL. « Ajouter un local à vélos dans le bâtiment 3 », « refaire
l'éclairage du parking » ou « planter des arbres dans les espaces verts » ne
concernent pas les mêmes voisins — et n'avaient aucun moyen de le dire.

L'idée était la dernière des trois entités de la Communauté à ne porter aucune
notion de lieu.

## La MÊME forme que partout ailleurs

Du JSON de codes (`["résidence"]`, `["bat:1","parking"]`), pas un texte libre.
`PerimetrePicker` et `perimetreLabel` ne savent lire que celle-là, et les
périmètres ont déjà divergé une fois (#316 : sept clés en dur dans `utils.ts`,
incapables de décrire une copropriété sans AFUL). Le sondage a été réaligné pour
cette raison le 16/08 (0147), l'annonce le 18/08 (0151) ; l'idée l'est ici.

⚠️ Ne PAS inventer une quatrième forme. C'est ce que le sondage avait fait
(`batiments_ids` + `profils_autorises`), et il a fallu une migration pour l'en
sortir.

## Les lignes existantes

`server_default` pose `["résidence"]` sur toutes les idées déjà déposées — c'est
ce que le produit leur appliquait de fait, puisqu'elles s'adressaient à tout le
monde. Le lecteur retombe donc exactement sur le comportement d'avant :
`estPerimetreParDefaut()` est vrai, et la carte n'affiche aucun badge 🔹. Une idée
existante ne change donc pas d'apparence.

Revision ID: 0153
Revises: 0152
"""
import sqlalchemy as sa
from alembic import op

revision = "0153"
down_revision = "0152"
branch_labels = None
depends_on = None

TABLE = "idee"
COLONNE = "perimetre_cible"


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    #  Idempotente : `start.sh` a `set -e`, et une migration qui rejoue sur une
    #  colonne déjà posée bloquerait le conteneur au démarrage.
    if COLONNE not in _colonnes(TABLE):
        op.add_column(
            TABLE,
            sa.Column(COLONNE, sa.String(), nullable=True, server_default='["résidence"]'),
        )


def downgrade() -> None:
    op.drop_column(TABLE, COLONNE)
