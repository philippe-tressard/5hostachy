"""Les Études & travaux reviennent au conseil syndical seul, choix explicites compris

Arbitré le 29/09/2026 : les Destinataires par défaut d'une Étude & travaux
sont « Conseil syndical seul » (`DEFAUT_PAR_CATEGORIE`,
`app/utils/visibility/defauts_affaire.py`). Les affaires restées au défaut s'y
rangent d'elles-mêmes : la règle se lit à chaque accès. Celles dont le conseil
avait CHOISI d'autres destinataires gardaient leur choix — l'utilisateur a
demandé de les ramener au conseil aussi.

Le choix est effacé (`NULL`), et non remplacé par `["conseil_syndical"]` : sans
choix, c'est la règle de la catégorie qui décide, et elle seule. Ne touche que
`public_cible`, et que les Études & travaux : ni l'actualité, ni une autre
catégorie. `confidentiel` n'est pas touché — il est plus étroit encore.

Idempotente : une affaire traitée n'a plus de destinataires, et n'est plus
sélectionnée.

`downgrade` ne restaure RIEN : les destinataires effacés ne sont conservés
nulle part, et rouvrir une étude à des lecteurs que la règle exclut n'est pas
un retour arrière, c'est la fuite que cette migration referme.

Revision ID: 0236
Revises: 0235
"""

import sqlalchemy as sa
from alembic import op

revision = "0236"
down_revision = "0235"
branch_labels = None
depends_on = None

CATEGORIE = "etude_travaux"


def upgrade() -> None:
    resultat = op.get_bind().execute(
        sa.text(
            "UPDATE ticket SET public_cible = NULL "
            "WHERE categorie = :categorie AND public_cible IS NOT NULL"
        ).bindparams(categorie=CATEGORIE)
    )
    #  Un nombre, jamais un identifiant ni un titre : ce que la MEP relit.
    print(f"0236 : {resultat.rowcount or 0} Étude(s) & travaux ramenée(s) au conseil seul")


def downgrade() -> None:
    pass
