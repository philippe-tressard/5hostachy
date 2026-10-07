"""L'activation de la relève des réponses par courriel s'écrit `"1"` ou `"0"` (#1718).

Le registre des services (`utils/services`) lit l'activation de TOUS les
services par une seule règle : seul `"1"` vaut oui. La relève IMAP en avait une
plus large — `"1"`, `"true"` ou `"oui"`, sans casse — écrite deux fois.

Ce lot ne doit changer l'état d'aucun service en production. Une base dont
`imap_enabled` vaudrait `"true"` ou `"oui"` aurait vu sa relève s'arrêter en
silence : la migration ramène ces valeurs à `"1"` AVANT que la règle unique ne
les lise. Les autres restent telles quelles — elles valaient « désactivé »
avant, et le valent toujours.

Les deux autres clés (`llm_actif`, `whatsapp_enabled`) étaient déjà lues
`== "1"` : y ramener `"true"` à `"1"` ALLUMERAIT un service éteint. Elles ne
sont pas touchées.

Revision ID: 0267
Revises: 0266
"""

import sqlalchemy as sa
from alembic import op

revision = "0267"
down_revision = "0266"
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().execute(
        sa.text(
            "UPDATE config_site SET valeur = :active "
            "WHERE cle = :cle AND lower(valeur) IN ('true', 'oui') "
        ).bindparams(active="1", cle="imap_enabled")
    )


def downgrade():
    #  Rien à défaire : `"1"` était déjà lu « activé » par l'ancienne règle.
    pass
