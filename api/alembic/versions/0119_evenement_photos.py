"""Photos sur les événements du calendrier.

Même convention que les tickets — colonne `photos_urls` contenant un tableau JSON
d'URLs internes — plutôt qu'un quatrième nom pour la même notion : le modèle
portait déjà `photos_urls` (ticket), `photos_json` et `images_json`. Le fil
d'activité sait déjà afficher `photos_urls`, il n'y a donc rien à écrire côté
rendu.

Idempotente (cf. 0117/0118) : la colonne n'est ajoutée que si elle manque.

Revision ID: 0119
Revises: 0118
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0119"
down_revision = "0118"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if "photos_urls" not in _colonnes("evenement"):
        op.add_column("evenement", sa.Column("photos_urls", sa.String(), nullable=True))


def downgrade():
    op.drop_column("evenement", "photos_urls")
