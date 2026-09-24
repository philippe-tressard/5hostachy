"""La marque « rédigé avec l'assistant IA » sur l'annonce de hall (#1089)

La 0194 a posé `assiste_ia` sur les neuf tables qui portaient une section
Description. L'annonce de hall n'en était pas : son écran montait un éditeur à
la main, sous l'intitulé « Message », sans l'assistant. Arbitré le 20/09/2026,
elle emploie désormais la section Description standard — assistant compris —,
et la règle de `utils/assiste_ia` s'applique : la marque est une colonne sur
chaque entité qui porte cette section.

`server_default="0"` : les annonces existantes n'ont pas été assistées, et une
colonne NOT NULL sans défaut ferait échouer l'ajout. Aucune clé étrangère
(interdite dans un `add_column` SQLite, cf. CLAUDE.md).

Revision ID: 0220
Revises: 0219
"""
import sqlalchemy as sa

from alembic import op

revision = "0220"
down_revision = "0219"
branch_labels = None
depends_on = None

TABLE = "annonce_hall"   # identifiant : constante du fichier, jamais une valeur liée
COLONNE = "assiste_ia"


def upgrade() -> None:
    colonnes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}
    if COLONNE in colonnes:
        return
    op.add_column(TABLE, sa.Column(COLONNE, sa.Boolean(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as lot:
        lot.drop_column(COLONNE)
