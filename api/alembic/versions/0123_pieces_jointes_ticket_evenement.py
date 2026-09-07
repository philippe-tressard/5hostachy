"""Pièces jointes documentaires sur les tickets et les affaires du calendrier.

Jusqu'ici, seules les photos pouvaient être jointes à la CRÉATION d'un ticket ou
d'une affaire : les documents (PDF, bureautique) n'étaient possibles qu'ensuite,
dans un commentaire. La colonne reprend le nom déjà porté par
`ticket_evolution.fichiers_urls`, `publication_evolution.fichiers_urls` et
`message_ticket.fichiers_urls` — un tableau JSON d'URLs internes — plutôt que
d'inventer un nom de plus pour la même notion.

`server_default` à `'[]'` : les lignes existantes doivent lire comme « aucune
pièce jointe », pas comme NULL, sinon chaque lecteur doit gérer les deux cas.

Idempotente (cf. 0117/0118/0119) : les colonnes ne sont ajoutées que si elles
manquent.

Revision ID: 0123
Revises: 0122
Create Date: 2026-08-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0123"
down_revision = "0122"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    for table in ("ticket", "evenement"):
        if "fichiers_urls" not in _colonnes(table):
            op.add_column(
                table,
                sa.Column(
                    "fichiers_urls",
                    sa.String(),
                    nullable=False,
                    server_default="[]",
                ),
            )


def downgrade():
    op.drop_column("evenement", "fichiers_urls")
    op.drop_column("ticket", "fichiers_urls")
