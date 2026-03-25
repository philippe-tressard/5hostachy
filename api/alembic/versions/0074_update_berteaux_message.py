"""Update Encombrants scheduled messages to multiline markdown format

Revision ID: 0074
Revises: 0073
Create Date: 2026-03-25
"""
from alembic import op

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None

NEW_BERTEAUX = (
    "Infos copro – Encombrants (*Rue Maurice Berteaux*)\n"
    "Collecte : *4ᵉ* samedi du mois, dès 6h*\n"
    "Sortie : la veille après 19h"
)
OLD_BERTEAUX = (
    "[Infos pour tous] - Pensez à sortir vos encombrants "
    "*Rue Maurice Berteaux*. La collecte des encombrants s'effectuera "
    "à partir de 6h, le 4ème samedi de chaque mois. "
    "Les sortir la veille après 19h. Merci."
)

NEW_HOSTACHY = (
    "Infos copro – Encombrants (*Boulevard Fernand Hostachy*)\n"
    "Collecte : *3ᵉ* samedi du mois, dès 6h*\n"
    "Sortie : la veille après 19h"
)
OLD_HOSTACHY = (
    "[Infos pour tous] - Pensez à sortir vos encombrants "
    "*Boulevard Fernand Hostachy*. La collecte des encombrants s'effectuera "
    "à partir de 6h, le 3ème samedi de chaque mois. "
    "Les sortir la veille après 19h. Merci."
)


def upgrade() -> None:
    op.execute(
        f"UPDATE whatsapp_scheduled SET message = '{NEW_BERTEAUX.replace(chr(39), chr(39)*2)}'"
        f" WHERE cron_rule = '4eme_samedi' AND label = 'Encombrants Rue Berteaux'"
    )
    op.execute(
        f"UPDATE whatsapp_scheduled SET message = '{NEW_HOSTACHY.replace(chr(39), chr(39)*2)}'"
        f" WHERE cron_rule = '3eme_samedi' AND label = 'Encombrants Bd Hostachy'"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE whatsapp_scheduled SET message = '{OLD_BERTEAUX.replace(chr(39), chr(39)*2)}'"
        f" WHERE cron_rule = '4eme_samedi' AND label = 'Encombrants Rue Berteaux'"
    )
    op.execute(
        f"UPDATE whatsapp_scheduled SET message = '{OLD_HOSTACHY.replace(chr(39), chr(39)*2)}'"
        f" WHERE cron_rule = '3eme_samedi' AND label = 'Encombrants Bd Hostachy'"
    )
