"""Le public visé resté d'une actualité ne suit pas l'affaire qu'elle est devenue (#1343)

Jusqu'au 26/09/2026, une affaire SUIVIE ignorait `public_cible` : seule
l'actualité le lisait. Une actualité promue en affaire pouvait donc garder le
sien sans effet. Depuis #1343, le conseil choisit les Destinataires d'une
affaire, et `ticket_visible` les honore : ce résidu se mettrait à décider qui
lit — un « Locataires » oublié ouvrirait l'affaire aux locataires.

Ce qui est effacé ne décidait RIEN jusqu'ici : la lecture de ces affaires ne
change pas. Irréversible par nature (on ne sait plus quel résidu était où) :
le `downgrade` ne restaure rien, et c'est sans perte, puisque rien ne le lisait.

Revision ID: 0228
Revises: 0227
"""

import sqlalchemy as sa
from alembic import op

revision = "0228"
down_revision = "0227"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE ticket SET public_cible = NULL "
            "WHERE categorie != :actualite AND public_cible IS NOT NULL"
        ).bindparams(actualite="actualite")
    )


def downgrade() -> None:
    pass
