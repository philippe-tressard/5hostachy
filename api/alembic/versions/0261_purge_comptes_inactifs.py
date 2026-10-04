"""La purge des comptes inactifs : la date d'avertissement (#1580)

La politique de confidentialité annonçait « données de compte actif : durée de
la relation + 2 ans », et aucun code ne l'appliquait. Arbitrage du 04/10/2026 :
un compte sans connexion depuis deux ans est averti par courriel, puis supprimé
trente jours plus tard s'il ne s'est pas reconnecté (`utils/purge_comptes`).

Deux gestes :

1. **`utilisateur.purge_avertie_le`** — la date de l'avertissement, sans laquelle
   aucune suppression n'a lieu. Colonne simple, nullable, sans contrainte : un
   `add_column` ne doit jamais en porter (0117, 0165).
2. **La politique servie le dit** : l'ancienne phrase (`CONSERVATION_COMPTES_ANCIEN`,
   posée par la 0029) est remplacée EXACTEMENT par la règle appliquée
   (`CONSERVATION_COMPTES`) — toutes deux lues dans le seed, jamais recopiées. Un
   texte reformulé depuis Admin › Légal n'est pas touché : l'administrateur y
   reporte alors la règle lui-même.

Le modèle d'e-mail de l'avertissement est un modèle AJOUTÉ : le seed le pose au
démarrage (`seed._poser_les_absents`), comme les derniers venus — aucune ligne ici.

Idempotente : la colonne n'est posée que si elle manque ; une fois la phrase
remplacée, l'ancienne ne figure plus.

⚠️ Les noms de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0261
Revises: 0258
"""

import sqlalchemy as sa

from alembic import op

revision = "0261"
down_revision = "0258"
branch_labels = None
depends_on = None

TABLE = "utilisateur"  # identifiants : constantes du fichier
COLONNE = "purge_avertie_le"


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade() -> None:
    conn = op.get_bind()
    if TABLE in set(sa.inspect(conn).get_table_names()) and COLONNE not in _colonnes(conn):
        op.add_column(TABLE, sa.Column(COLONNE, sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if TABLE in set(sa.inspect(conn).get_table_names()) and COLONNE in _colonnes(conn):
        with op.batch_alter_table(TABLE) as lot:
            lot.drop_column(COLONNE)
