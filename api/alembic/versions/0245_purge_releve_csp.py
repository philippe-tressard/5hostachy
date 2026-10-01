"""Le relevé des violations CSP est retiré : sa clé de configuration aussi (01/10/2026)

Le point de collecte `/csp-report`, l'écran `Admin → Sécurité (CSP)` et
l'en-tête `Report-Only` qui l'alimentait ont été retirés ensemble : chaque
directive utile est passée en bloquant sur la foi du relevé (#536, #770), et il
ne mesurait plus que `img-src`, dont les seules violations venaient d'une
extension de navigateur.

Le relevé persistait dans `config_site` sous `csp_violations` (directive et
ressource refusée, agrégées). Plus rien ne le lit : la ligne s'efface plutôt
que de rester comme une donnée sans lecteur.

Pas de retour : la valeur était un compteur d'observation, la rétablir vide
serait mentir sur ce qu'elle contenait.

Revision ID: 0245
Revises: 0244
"""

import sqlalchemy as sa
from alembic import op

revision = "0245"
down_revision = "0244"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM config_site WHERE cle = :cle").bindparams(cle="csp_violations")
    )


def downgrade() -> None:
    pass
