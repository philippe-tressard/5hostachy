"""Une affiche de hall se rattache à l'affaire « Actualité » qui l'a produite (#1091).

`AnnonceHall.publication_id` la rattachait à une publication. L'actualité devient
une affaire : la colonne `ticket_id` porte désormais ce lien — un mot par notion,
plutôt que `publication_id` réemployé pour un identifiant d'affaire.

Sans clé étrangère, comme `publication_id` (0117 : SQLite refuse d'altérer les
contraintes d'une table existante). Le report des liens existants est fait par la
migration de données 0210.
"""
import sqlalchemy as sa
from alembic import op

revision = "0209"
down_revision = "0208"
branch_labels = None
depends_on = None

#: L'identifiant ne peut pas se lier en SQLite : il vient de ces constantes.
TABLE = "annonce_hall"
COLONNE = "ticket_id"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    if COLONNE not in _colonnes(op.get_bind()):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer(), nullable=True))


def downgrade():
    if COLONNE in _colonnes(op.get_bind()):
        with op.batch_alter_table(TABLE) as lot:
            lot.drop_column(COLONNE)
