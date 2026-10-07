"""La rubrique de la FAQ qui parle du logiciel ne porte plus le nom de la résidence (#1725).

Elle s'appelait « 📱 Application 5Hostachy » : le nom de CETTE copropriété,
que le seed posait dans la FAQ de toute autre installation. Le seed dit
désormais « 📱 L'application » (`seed/faq.CATEGORIE_APPLICATION`).

La base suit, et ce n'est pas cosmétique : `FAQ_COMPLEMENTAIRE` ajoute ses
questions sous la catégorie du seed. Sans ce renommage, la prochaine question
complémentaire ouvrirait une SECONDE rubrique à côté de l'ancienne.

Seule la catégorie change ; les réponses — qui peuvent nommer la résidence,
à juste titre dans cette base — ne sont pas touchées.

Revision ID: 0268
Revises: 0267
"""

import sqlalchemy as sa
from alembic import op

revision = "0268"
down_revision = "0267"
branch_labels = None
depends_on = None

ANCIENNE = "📱 Application 5Hostachy"
NOUVELLE = "📱 L'application"


def upgrade():
    op.get_bind().execute(
        sa.text("UPDATE faq_item SET categorie = :nouvelle WHERE categorie = :ancienne").bindparams(
            nouvelle=NOUVELLE, ancienne=ANCIENNE
        )
    )


def downgrade():
    op.get_bind().execute(
        sa.text("UPDATE faq_item SET categorie = :ancienne WHERE categorie = :nouvelle").bindparams(
            nouvelle=NOUVELLE, ancienne=ANCIENNE
        )
    )
