"""`ticket.epingle` — un ticket peut être maintenu en tête de liste

## Pourquoi (05/09/2026, demandé à l'écran)

> « tous les autres options de publication doivent être aussi conservé dans
>   l'objet pour les tickets en édition et commentaire »
> « pas que Visibilité du ticket »

Le ticket ne portait qu'une option de publication (🛡️ « Visibilité au seul
conseil syndical », colonne `confidentiel`). L'actualité en porte quatre. Cette
migration apporte la seule qui manquait VRAIMENT — les deux autres existaient
déjà sous un autre nom, ou n'auraient rien fait :

| Option | Sur un ticket |
|---|---|
| 📌 Épingler | **cette colonne** |
| 🚨 Marquer urgente | `priorite = haute`, ce que fait déjà la catégorie « Urgence » — la case pilote cette colonne, pour qu'un ticket ne soit pas urgent d'un côté et normal de l'autre |
| 🛡️ Conseil syndical | `confidentiel`, depuis #710 |
| 🔒 Visible du seul périmètre | **déjà le cas** : `ticket_visible` appelle `perimetre_visible` sans `ouvert_a_la_copropriete`, là où une actualité le passe (#339). Une case n'aurait rien restreint |

## Colonne simple, sans contrainte

Pas de `ForeignKey`, pas d'index : SQLite refuse d'altérer les contraintes d'une
table existante, et une migration qui crashe APRÈS avoir ajouté la colonne bloque
le conteneur au démarrage (`start.sh` a `set -e`). C'est arrivé deux fois — 0117
et 0165.

Revision ID: 0175
Revises: 0174
Create Date: 2026-09-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0175"
down_revision = "0174"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    #  Idempotente : le conteneur rejoue les migrations à chaque démarrage.
    if "epingle" in _colonnes("ticket"):
        return
    op.add_column(
        "ticket",
        sa.Column("epingle", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    if "epingle" in _colonnes("ticket"):
        op.drop_column("ticket", "epingle")
