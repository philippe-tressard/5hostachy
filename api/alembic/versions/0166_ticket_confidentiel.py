"""`ticket.confidentiel` — le FILET, posé AVANT l'ouverture en lecture

#710, étape 1 du découpage que le ticket propose lui-même.

## Pourquoi maintenant, et pas avec l'ouverture

L'ouverture des tickets aux résidents de leur périmètre est décidée. Elle rendrait
lisibles de tout un bâtiment des affaires qui parlent de personnes : un litige de
voisinage, un impayé, un dégât des eaux qui nomme quelqu'un.

> **Ouvrir la lecture sans pouvoir refermer un cas particulier est un choix
> irréversible sur des données qui parlent de personnes.**

D'où l'ordre : le drapeau d'abord, l'ouverture ensuite. À ce stade **personne ne
voit rien de plus** — `ticket_visible()` reste binaire (auteur, personne pour qui
le ticket a été saisi, CS, admin). Le filet est tendu avant qu'on marche dessus.

## Le défaut est `false`, comme pour les actualités

Un ticket n'est pas confidentiel jusqu'à preuve du contraire. C'est le choix déjà
fait pour `Publication.confidentiel` (#347), et refaire le même ici évite deux
réponses à une seule question. Le CS marque les cas qui le demandent.

⚠️ Conséquence à assumer, et c'est bien de l'écrire : **les tickets existants
restent tous non confidentiels**. Il faudra les relire avant d'ouvrir la lecture —
c'est l'objet de l'étape 2, pas de celle-ci.

## Aucune contrainte, et la garde d'idempotence

Un booléen : rien à contraindre. La garde `_colonnes` est celle de 0165 et 0117,
qui ont toutes deux crashé en production faute de l'avoir — `start.sh` a `set -e`,
et un `add_column` sur une colonne existante bloque le conteneur au démarrage.

⚠️ `server_default` est posé : sans lui, les lignes existantes prendraient NULL,
et SQLModel lirait `None` là où il attend un booléen. Le défaut Python (`False`)
ne s'applique qu'aux lignes écrites APRÈS, par l'application.

Revision ID: 0166
Revises: 0165
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from alembic import op

revision = "0166"
down_revision = "0165"
branch_labels = None
depends_on = None


def _colonnes(nom_table: str) -> set[str]:
    """Les colonnes présentes — la migration doit pouvoir se rejouer."""
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(nom_table)}


def upgrade():
    if "confidentiel" not in _colonnes("ticket"):
        op.add_column(
            "ticket",
            sa.Column(
                "confidentiel",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade():
    if "confidentiel" in _colonnes("ticket"):
        op.drop_column("ticket", "confidentiel")
