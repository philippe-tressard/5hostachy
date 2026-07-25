"""Photos des annonces de hall : liste de photos, plus d'illustration principale.

Le texte de l'affiche est l'élément central ; les photos sont facultatives et
limitées (cf. `MAX_PHOTOS`), placées en pied de contenu.

Idempotente pour la même raison que 0117 (cf. son en-tête).

Revision ID: 0118
Revises: 0117
Create Date: 2026-07-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0118"
down_revision = "0117"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    colonnes = _colonnes("annonce_hall")
    if "images_json" not in colonnes:
        op.add_column(
            "annonce_hall",
            sa.Column("images_json", sa.String(), nullable=False, server_default="[]"),
        )
    if "image_url" in colonnes:
        op.drop_column("annonce_hall", "image_url")


def downgrade():
    op.add_column("annonce_hall", sa.Column("image_url", sa.String(), nullable=True))
    op.drop_column("annonce_hall", "images_json")
