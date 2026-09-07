"""`perimetre.privatif` — distinguer un espace PRIVATIF des parties communes

Demandé le 31/08/2026 :

> *« pour l'objet Périmètre, distinguer les périmètres PRIVATIF […] dans
> Admin/Périmètre prévoir à la saisie un paramètre Privatif pour rendre privatif
> un périmètre (Exemple : Logement) »*

L'arborescence n'avait pas de mot pour cette distinction : « Logement » y
voisinait « Hall d'entrée » sans que rien ne dise que l'un est chez quelqu'un et
l'autre à tout le monde. C'est pourtant la question qu'on se pose en premier
devant une demande.

⚠️ **`False` par défaut, et aucune donnée n'est devinée.** Il aurait été tentant
de cocher « Logement » au passage — mais l'arborescence est administrable, et
chaque copropriété nomme ses espaces comme elle veut. Deviner d'après un libellé
marcherait ici et se tromperait ailleurs. C'est à l'administrateur de le dire,
depuis l'écran prévu pour.

Revision ID: 0163
Revises: 0162
"""
import sqlalchemy as sa
from alembic import op

revision = "0163"
down_revision = "0162"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "perimetre",
        sa.Column("privatif", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("perimetre", "privatif")
