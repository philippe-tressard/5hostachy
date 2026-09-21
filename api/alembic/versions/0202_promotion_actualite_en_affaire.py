"""D'où vient une affaire née d'une actualité (#1094).

## Pourquoi (chantier v2.0.0)

Aujourd'hui, une actualité qui dérape — « attention, fuite au 3e » — oblige à
rouvrir une affaire et **tout retaper**. Après ce lot, un bouton la promeut :
titre, description, pièces jointes et périmètre suivent, et l'on ajoute un
statut.

Arbitré le 21/09/2026 : la publication d'origine **disparaît du fil**. Un seul
objet à la fois, jamais de doublon — c'est ce que « le suivi devient une
propriété » veut dire à l'écran.

## 🔴 Ce que cette colonne empêche : le lien mort

Une actualité publiée a déjà été **envoyée par courriel**, avec son adresse
`/actualites#pub-42`. La supprimer sans rien laisser derrière ferait de chacun
de ces courriels un lien mort — et ils sont dans des boîtes depuis des mois,
exactement comme les identifiants `TK-xxxx` que le chantier refuse de renommer
pour la même raison.

`promu_depuis_publication_id` garde le numéro de la publication disparue. C'est
lui qui permet à l'ancienne adresse de mener à l'affaire née d'elle.

## ⚠️ Pas de `ForeignKey`, et ce n'est pas un oubli

Deux raisons, chacune suffisante :

1. **La ligne référencée n'existe plus** — c'est le principe même de la
   promotion. Une contrainte serait violée à l'instant où elle servirait : ce
   champ est un identifiant *historique*, pas un lien vivant.
2. **SQLite ne sait pas ajouter une contrainte par `ALTER`.** La migration
   crasherait *après* avoir posé la colonne, et `start.sh` (`set -e`)
   bloquerait le conteneur — c'est arrivé deux fois, 0117 et 0165.
   `api/tests/test_migrations.py` refuse les deux.

## Ce que cette migration ne fait PAS

Elle ne touche à aucune donnée existante : une colonne nullable s'ajoute, et
toutes les affaires déjà en base la portent à `NULL` — ce qui est exact, aucune
n'est née d'une actualité.

⚠️ `add_column` sur une colonne existante lève, et `start.sh` a `set -e` : la
garde d'idempotence est ce qui permet à la migration de se rejouer sans bloquer
le conteneur.
"""
import sqlalchemy as sa
from alembic import op

revision = "0202"
down_revision = "0201"
branch_labels = None
depends_on = None

#: Les identifiants ne peuvent pas se lier en SQLite : ils s'interpolent depuis
#: ces constantes, jamais depuis une donnée (`CLAUDE.md`, conventions Alembic).
TABLE_TICKET = "ticket"
COLONNE = "promu_depuis_publication_id"
INDEX = "ix_ticket_promu_depuis_publication_id"


def _colonnes(nom_table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(nom_table)}


def _index(nom_table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(nom_table)}


def upgrade() -> None:
    if COLONNE not in _colonnes(TABLE_TICKET):
        op.add_column(TABLE_TICKET, sa.Column(COLONNE, sa.Integer(), nullable=True))
    #  Indexé : c'est la clé de la redirection depuis l'ancienne adresse, donc
    #  une lecture par cette colonne à chaque courriel ancien qu'on rouvre.
    if INDEX not in _index(TABLE_TICKET):
        op.create_index(INDEX, TABLE_TICKET, [COLONNE])


def downgrade() -> None:
    #  L'index d'abord : SQLite refuse de retirer une colonne qu'un index porte.
    if INDEX in _index(TABLE_TICKET):
        op.drop_index(INDEX, table_name=TABLE_TICKET)
    if COLONNE in _colonnes(TABLE_TICKET):
        op.drop_column(TABLE_TICKET, COLONNE)
