"""La fiche d'un prestataire : adresse, description, et la marque de l'assistant (#1327)

Arbitré à l'écran le 25/09/2026 : l'adresse de l'entreprise (facultative, dans la
section Contacts) et une description (section rouverte, avec l'assistant ✨). Toute
entité qui porte une section Description porte la marque `assiste_ia`
(`utils/assiste_ia`) : `server_default="0"`, car les fiches existantes n'ont pas
été assistées, et une colonne NOT NULL sans défaut ferait échouer l'ajout.

Idempotente : une colonne déjà présente n'est pas reposée. Aucune clé étrangère
(interdite dans un `add_column` SQLite, cf. CLAUDE.md).

Revision ID: 0225
Revises: 0224
"""

import sqlalchemy as sa

from alembic import op

revision = "0225"
down_revision = "0224"
branch_labels = None
depends_on = None

TABLE = "prestataire"  # identifiant : constante du fichier
COLONNES = (
    ("adresse", sa.Text(), {"nullable": True}),
    ("description", sa.Text(), {"nullable": True}),
    ("assiste_ia", sa.Boolean(), {"nullable": False, "server_default": "0"}),
)


def upgrade() -> None:
    presentes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}
    for nom, type_, options in COLONNES:
        if nom not in presentes:
            op.add_column(TABLE, sa.Column(nom, type_, **options))


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as lot:
        for nom, _type, _options in reversed(COLONNES):
            lot.drop_column(nom)
