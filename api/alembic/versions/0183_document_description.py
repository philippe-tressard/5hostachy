"""Un document porte une DESCRIPTION (#852).

Demandé à l'écran le 08/09/2026, sur la page Résidence :

> *« très peu de champs sont éditables, et notamment les PJ ; […] ajouter aussi
> un champ descriptif »*

## Ce que la colonne ajoute, et ce qu'elle ne double pas

Le **titre** nomme le document ; la **description** dit ce qu'il couvre, d'où il
vient et ce qu'il ne dit pas. Sur un règlement de copropriété, c'est la différence
entre « Règlement 2024 » et « remplace celui de 1998 ; les annexes 3 et 4 sont
chez le syndic ».

C'est la **section 6** du cadre (`ux-patterns` §0), et le document était l'une des
dernières entités du site à ne pas la porter.

⚠️ **Pas de `ForeignKey` dans un `add_column`** — SQLite refuse d'altérer les
contraintes d'une table existante, la migration crasherait *après* avoir ajouté la
colonne, et `start.sh` (`set -e`) bloquerait le conteneur. C'est arrivé deux fois
(0117, 0165). Ici c'est du texte : la question ne se pose pas, mais la garde
d'idempotence reste, pour la même raison.

Revision ID: 0183
Revises: 0182
Create Date: 2026-09-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0183"
down_revision = "0182"
branch_labels = None
depends_on = None


def _colonnes() -> set[str]:
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns("document")}


def upgrade() -> None:
    #  Garde d'idempotence : un redémarrage qui rejoue la migration ne doit pas
    #  échouer sur une colonne déjà posée.
    if "description" not in _colonnes():
        op.add_column(
            "document",
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
        )


def downgrade() -> None:
    if "description" in _colonnes():
        op.drop_column("document", "description")
