"""L'affaire porte l'équipement concerné, posé par le conseil (#1097).

Le décret n° 2001-477 attend d'un carnet d'entretien qu'il dise quels travaux,
**sur quoi**, par qui. « Sur quoi » manquait : `TypeEquipement` vivait chez les
contrats, pas sur l'affaire.

Colonne simple, **sans clé étrangère** ni contrainte : la valeur est vérifiée
par `utils/intervenant` (liste blanche `EQUIPEMENTS_AFFAIRE`).
"""
import sqlalchemy as sa
from alembic import op

revision = "0216"
down_revision = "0215"
branch_labels = None
depends_on = None

TABLE = "ticket"
#  Identifiant de colonne : constante de ce fichier, jamais une saisie.
COLONNE = "equipement"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    if COLONNE not in _colonnes(op.get_bind()):
        op.add_column(TABLE, sa.Column(COLONNE, sa.String(), nullable=True))


def downgrade():
    if COLONNE in _colonnes(op.get_bind()):
        with op.batch_alter_table(TABLE) as lot:
            lot.drop_column(COLONNE)
