"""Le périmètre d'une évolution de ticket — il se précise à mesure qu'on cherche.

Demandé le 19/08/2026, sur un cas réel :

> *« Évolution d'un commentaire — historique d'un ticket : il faudrait ajouter la
> section périmètre, car dans l'exemple #TK-427648 le périmètre de la fuite
> pourrait être précisée et évolue. »*

## Pourquoi le périmètre ne peut pas rester figé à l'ouverture

Un ticket se signale avec ce qu'on sait **au moment où on le signale** — donc
souvent avec le périmètre le plus large, parce qu'on ignore encore d'où ça vient.
« Il y a une fuite dans le bâtiment 2. » Puis on cherche, et on sait : 3ᵉ étage,
cage B.

Jusqu'ici cette précision se perdait, ou se racontait en texte libre dans un
commentaire. Le périmètre affiché restait celui de l'ouverture — donc **faux** dès
la deuxième évolution, sur les cartes, dans les listes, et dans le message
WhatsApp que le fil envoie au groupe.

## La colonne est SANS `server_default`, contrairement aux quatre précédentes

Migrations 0147 (sondage), 0151 (annonce), 0153 (idée) : toutes posent
`["résidence"]` sur les lignes existantes, parce que ces objets **ont** un
périmètre — il valait « toute la résidence » sans le dire.

Ici, non. Une évolution n'a pas de périmètre : elle en **déclare** un, ou elle
n'en parle pas. `NULL` veut dire « cette entrée ne dit rien du périmètre », et
c'est le cas de l'immense majorité des commentaires. Poser `["résidence"]`
partout ferait croire que chaque commentaire a élargi le ticket à toute la
copropriété — l'inverse exact de ce qu'on cherche à écrire.

⚠️ C'est la première fois qu'une colonne de périmètre est ajoutée sans défaut
dans ce dépôt. La différence n'est pas technique, elle est de sens : les autres
décrivent **un objet**, celle-ci décrit **un changement**.

## La MÊME forme partout ailleurs

Du JSON de codes (`["résidence"]`, `["bat:1","parking"]`), pas un texte libre.
`PerimetrePicker` et `perimetreLabel` ne savent lire que celle-là, et les
périmètres ont déjà divergé une fois (#316). Ne PAS inventer une cinquième forme.

## Le périmètre courant du ticket suit

`add_evolution` reporte le périmètre déclaré sur `ticket.perimetre_cible`. Le
« périmètre courant est celui de la dernière évolution qui en déclare un » devient
alors un fait, sans aucun calcul à la lecture : les cartes, les listes, les
e-mails et le message WhatsApp — qui lisent tous `ticket.perimetre_cible` —
deviennent justes du même coup, sans être touchés.

L'historique, lui, reste ici : chaque évolution garde ce qu'elle a déclaré.

Revision ID: 0154
Revises: 0153
"""
import sqlalchemy as sa
from alembic import op

revision = "0154"
down_revision = "0153"
branch_labels = None
depends_on = None

TABLE = "ticket_evolution"
COLONNE = "perimetre_cible"


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    #  Idempotente : `start.sh` a `set -e`, et une migration qui rejoue sur une
    #  colonne déjà posée bloquerait le conteneur au démarrage.
    if COLONNE not in _colonnes(TABLE):
        op.add_column(TABLE, sa.Column(COLONNE, sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE, COLONNE)
