"""0031 — Fix FAQ PWA answer: texte simplifié sans jargon technique"""

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import text

NEW_REPONSE = (
    "5Hostachy est une application compatible PC, tablette et mobile "
    "nécessitant une connexion internet. Elle peut s'installer sur l'écran "
    "d'accueil de votre téléphone comme une vraie app, mais les fonctions "
    "principales (tickets, messagerie, documents) restent inaccessibles sans réseau."
)


def upgrade():
    op.execute(
        text("UPDATE faq_item SET reponse = :r WHERE question LIKE :q").bindparams(
            r=NEW_REPONSE,
            q="%hors connexion%",
        )
    )


def downgrade():
    pass
