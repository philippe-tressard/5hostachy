"""La section « Quand » : une actualité et une affaire peuvent porter une date (#1092).

## Pourquoi (chantier v2.0.0)

Trois objets deviennent deux — **Actualité** et **Affaire**. Le Calendrier cesse
d'être un objet pour devenir une **vue** : « tout ce qui porte une date », comme
le carnet d'entretien est déjà une vue sur trois tables.

Pour cela, une publication et un ticket doivent pouvoir dire *quand*. Jusqu'ici
seul `Evenement` le pouvait (`debut`, `fin`), et c'est ce qui obligeait à créer
un troisième objet pour une simple coupure d'eau.

## Les colonnes, et les deux notions à ne pas confondre

| Colonne | Sens | Sur |
|---|---|---|
| `debut`, `fin` | *ça se passe le X* — alimente le calendrier | publication **et** ticket |
| `echeance` | *ça doit être fait avant le X* — alimente le suivi | ticket **seulement** |

Une actualité n'a pas d'échéance : elle ne se suit pas. Poser la colonne quand
même aurait ouvert la porte à un champ d'écran que rien ne consomme — ce que le
cadre #430 interdit en toutes lettres.

🔴 **Les noms `debut` et `fin` sont ceux d'`Evenement`, et c'est délibéré.** Le
lot qui fera disparaître l'entité recopiera ses lignes dans `publication` : des
colonnes homonymes rendent cette reprise littérale, là où `evenement_debut`
aurait imposé une table de correspondance à écrire — donc à faire diverger.

## Ce que cette migration ne fait PAS

Elle **ne touche à rien d'existant** : ni `Evenement`, ni le calendrier, ni le
carnet. Trois colonnes nullables s'ajoutent, et tout continue exactement comme
avant. La bascule du calendrier en vue, puis la disparition de l'entité, sont
deux lots distincts — l'empreinte d'`Evenement` est de 7 184 lignes côté API et
36 fichiers côté front, mesurée le 20/09/2026.

⚠️ `add_column` sur une colonne existante lève, et `start.sh` a `set -e` : la
garde d'idempotence n'est pas décorative, elle est ce qui permet à la migration
de se rejouer sans bloquer le conteneur (leçon des migrations 0117 et 0165).
"""
import sqlalchemy as sa
from alembic import op

revision = "0200"
down_revision = "0199"
branch_labels = None
depends_on = None

#: Les identifiants ne peuvent pas se lier en SQLite : ils s'interpolent depuis
#: ces constantes, jamais depuis une donnée (`CLAUDE.md`, conventions Alembic).
TABLE_PUBLICATION = "publication"
TABLE_TICKET = "ticket"


def _colonnes(nom_table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(nom_table)}


def _ajouter(nom_table: str, colonne: sa.Column) -> None:
    if colonne.name not in _colonnes(nom_table):
        op.add_column(nom_table, colonne)


def upgrade() -> None:
    #  « ça se passe le X » — les deux objets.
    for table in (TABLE_PUBLICATION, TABLE_TICKET):
        _ajouter(table, sa.Column("debut", sa.DateTime(), nullable=True))
        _ajouter(table, sa.Column("fin", sa.DateTime(), nullable=True))
    #  « ça doit être fait avant le X » — l'affaire seulement.
    _ajouter(TABLE_TICKET, sa.Column("echeance", sa.Date(), nullable=True))


def downgrade() -> None:
    #  SQLite sait retirer une colonne depuis la 3.35 ; la garde reste, pour que
    #  le retour en arrière ne dépende pas de l'ordre où il est joué.
    for table, colonnes in (
        (TABLE_TICKET, ("echeance", "fin", "debut")),
        (TABLE_PUBLICATION, ("fin", "debut")),
    ):
        presentes = _colonnes(table)
        for nom in colonnes:
            if nom in presentes:
                op.drop_column(table, nom)
