"""La clé du bridge WhatsApp quitte la base : elle n'a plus qu'une source, `.env` (02/10/2026)

La clé était écrite DEUX fois (#1596) : dans `.env` (`WHATSAPP_API_KEY`), que
compose donne au bridge, et dans `config_site` sous `whatsapp_api_key`, saisie à
l'écran d'administration et lue par l'API. Rien ne les confrontait : un écart
ne se voyait qu'au 401 de l'envoi.

L'API lit désormais la variable d'environnement (`Settings.whatsapp_api_key`,
par `utils/whatsapp.entetes_bridge`), et l'enregistrement de la configuration
refuse la clé. La ligne de la base n'a donc plus de lecteur — et un secret sans
lecteur reste un secret : il voyage avec chaque sauvegarde, chaque réplication
vers le standby et chaque copie hors site. Elle s'efface.

Pas de retour : la valeur faisait double emploi avec `.env`, qui fait foi. La
rétablir recréerait la seconde écriture que ce lot supprime.

Revision ID: 0249
Revises: 0248
"""

import sqlalchemy as sa
from alembic import op

revision = "0249"
down_revision = "0248"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM config_site WHERE cle = :cle").bindparams(cle="whatsapp_api_key")
    )


def downgrade() -> None:
    pass
