"""Actualité confidentielle : le périmètre redevient restrictif (#347).

Depuis #339 (v2.62.0), une actualité ciblée sur un bâtiment reste lisible de
toute la copropriété : le périmètre dit *de quoi ça parle*, plus *qui peut le
lire*. `publication.confidentiel` rend le périmètre restrictif **pour cette
publication-là**.

La valeur par défaut est **faux**, et c'est la seule valeur défendable : aucune
actualité existante n'a été écrite en supposant une lecture restreinte, et
restreindre après coup ferait disparaître du fil des contenus que des résidents
ont déjà vus. Le drapeau ne fait que retirer de la visibilité — il n'en accorde
jamais (`api/tests/test_visibilite_ouverte.py`).

Idempotente : un ajout de colonne interrompu avant l'enregistrement de la
révision laisse la colonne en place ; le rejeu au démarrage suivant échouerait
sur « duplicate column name » et bloquerait l'API en boucle de crash (incident
du 25/07/2026, cf. migration 0117).

Revision ID: 0146
Revises: 0145
Create Date: 2026-08-15
"""
import sqlalchemy as sa
from alembic import op

revision = "0146"
down_revision = "0145"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if "confidentiel" not in _colonnes("publication"):
        op.add_column(
            "publication",
            sa.Column("confidentiel", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade():
    op.drop_column("publication", "confidentiel")
