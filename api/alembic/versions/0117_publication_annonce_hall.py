"""Annonce de hall générée depuis une actualité.

- `publication.annonce_hall` : option de publication (comme partager_whatsapp / envoyer_cs)
- `annonce_hall.publication_id` : traçabilité de l'actualité d'origine

Idempotente : un ajout de colonne interrompu avant l'enregistrement de la
révision dans `alembic_version` laisse la colonne en place ; le rejeu au
démarrage suivant échouerait alors sur « duplicate column name » et bloquerait
l'API en boucle de crash (incident du 25/07/2026).

Revision ID: 0117
Revises: 0116
Create Date: 2026-07-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0117"
down_revision = "0116"
branch_labels = None
depends_on = None


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    if "annonce_hall" not in _colonnes("publication"):
        op.add_column(
            "publication",
            sa.Column("annonce_hall", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "publication_id" not in _colonnes("annonce_hall"):
        op.add_column(
            "annonce_hall",
            #  🔴 AUCUNE `ForeignKey` ici, et c'est un CORRECTIF du 01/09/2026 :
            #  SQLite refuse d'ajouter une contrainte à une table existante, et
            #  cette ligne la posait. Elle a donc crashé au déploiement du
            #  25/07/2026 — `NotImplementedError: No support for ALTER of
            #  constraints in SQLite dialect` — après avoir exécuté le `ADD
            #  COLUMN`. Personne ne l'a vu : `start.sh` a `set -e`, le conteneur
            #  est reparti, et la garde d'idempotence ci-dessus a laissé passer le
            #  second essai. La colonne existe partout, sans sa contrainte.
            #
            #  Trouvée cinq semaines plus tard par `test_aucune_cle_etrangere_dans_un_add_column`,
            #  écrit pour le même défaut commis dans la migration 0165.
            sa.Column("publication_id", sa.Integer(), nullable=True),
        )


def downgrade():
    op.drop_column("annonce_hall", "publication_id")
    op.drop_column("publication", "annonce_hall")
