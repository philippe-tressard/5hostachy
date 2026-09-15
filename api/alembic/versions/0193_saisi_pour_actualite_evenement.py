"""« Saisi pour » sur les actualités et les événements.

## Ce que cette migration pose

Les trois colonnes que `Ticket` porte déjà — `saisi_pour_user_id`,
`saisi_pour_nom`, `saisi_pour_email` — sur `publication` et `evenement`. Même
notion, même stockage : un membre du conseil syndical peut désormais déposer une
actualité ou un événement **au nom de quelqu'un d'autre**, comme il le fait
depuis toujours pour un ticket.

## 🔴 Elle étend un DROIT, et il faut le dire

`auth/deps.py::est_auteur` lit `saisi_pour_user_id` par `getattr`, sans connaître
le type de l'objet. Poser la colonne suffit donc à ce que la personne nommée
puisse **corriger** l'actualité ou l'événement qui parle d'elle.

C'est la règle voulue (`ux-patterns` §15 : *un membre du CS qui dépose au nom
d'un résident ne le dépossède pas de sa demande*) — mais c'est une conséquence
d'une migration de schéma, pas une ligne de code qu'on relit. Elle est écrite
ici, dans les deux modèles, et `test_saisi_pour_actualite_evenement.py`
l'éprouve.

## ⚠️ Aucune clé étrangère, et c'est obligatoire

SQLite refuse d'ajouter une contrainte à une table existante :
`op.add_column(..., sa.ForeignKey(...))` crashe **après** avoir exécuté le
`ADD COLUMN`, laissant la colonne sans sa contrainte et la révision non marquée.
`start.sh` a `set -e`, donc le conteneur s'arrête. C'est arrivé deux fois (0117,
0165) sans que personne le voie.

Les modèles ne déclarent donc pas `foreign_key=` non plus : une base neuve
(`create_all`) et une base migrée doivent porter le **même** schéma.
`test_migrations.py` refuse les deux moitiés de ce défaut.

Revision ID: 0193
Revises: 0192
Create Date: 2026-09-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0193"
down_revision = "0192"
branch_labels = None
depends_on = None

#: Les mêmes trois colonnes sur les deux tables. Écrites UNE fois : les recopier
#: par table est exactement ce qui fait diverger deux schémas qui doivent être
#: identiques.
COLONNES = (
    ("saisi_pour_user_id", sa.Integer()),
    ("saisi_pour_nom", sa.String()),
    ("saisi_pour_email", sa.String()),
)
TABLES = ("publication", "evenement")


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    #  Garde d'idempotence : `start.sh` a `set -e`, et une migration qui crashe
    #  laisse le conteneur bloqué au démarrage. Une colonne déjà posée — par un
    #  passage précédent interrompu — ne doit pas faire tomber le suivant.
    for table in TABLES:
        presentes = _colonnes(table)
        for nom, type_ in COLONNES:
            if nom not in presentes:
                op.add_column(table, sa.Column(nom, type_, nullable=True))


def downgrade() -> None:
    for table in TABLES:
        presentes = _colonnes(table)
        for nom, _ in COLONNES:
            if nom in presentes:
                op.drop_column(table, nom)
