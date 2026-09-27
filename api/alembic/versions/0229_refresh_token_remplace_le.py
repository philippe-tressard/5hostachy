"""Quand un jeton de rafraîchissement a été échangé — pour reconnaître un jeton rejoué

`/auth/refresh` révoque le jeton qu'il échange. Un jeton déjà échangé qui
revient est le signal d'un vol, et ferme toutes les sessions du compte
(`auth/jetons_rafraichissement.py`). Encore faut-il le distinguer d'un jeton
révoqué par une déconnexion ou un mot de passe posé : c'est cette colonne.

Nullable et sans défaut : les jetons existants n'ont pas été échangés sous
cette règle, et `NULL` les range parmi les révocations ordinaires.

Idempotente : une colonne déjà présente n'est pas reposée. Aucune clé étrangère.

Revision ID: 0229
Revises: 0228
"""

import sqlalchemy as sa

from alembic import op

revision = "0229"
down_revision = "0228"
branch_labels = None
depends_on = None

TABLE = "refresh_token"  # identifiant : constante du fichier
COLONNE = "remplace_le"


def upgrade() -> None:
    presentes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(TABLE)}
    if COLONNE not in presentes:
        op.add_column(TABLE, sa.Column(COLONNE, sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as lot:
        lot.drop_column(COLONNE)
