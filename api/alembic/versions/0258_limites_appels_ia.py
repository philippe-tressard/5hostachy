"""Le plafond mensuel de l'assistant IA se compte en APPELS, plus en jetons (04/10/2026)

Le plafond se saisissait en jetons par mois (#1383) : un chiffre que personne
ne sait estimer — « 100000 » ne dit pas combien de synthèses il permet. Il est
remplacé par deux nombres d'appels par usage, `llm_<usage>_appels_mois` et
`llm_<usage>_appels_heure` (par personne), et le coût du premier essai chiffre
ce que la limite laisse dépenser (`utils/llm_limites`).

Cette migration RETIRE les clés `llm_<usage>_plafond_mois` : un nombre de
jetons ne se convertit pas en nombre d'appels — il faudrait connaître la taille
d'un appel, que seul le premier essai donnera. Absentes, les nouvelles clés
valent « aucune limite » : les nombres d'appels se saisissent dans
Administration › Assistant IA.

Revision ID: 0258
Revises: 0257
"""

import sqlalchemy as sa

from alembic import op

revision = "0258"
down_revision = "0257"
branch_labels = None
depends_on = None

#: `_` est un joker de LIKE : échappé, pour ne viser que le suffixe exact.
MOTIF = r"llm\_%\_plafond\_mois"


def upgrade() -> None:
    conn = op.get_bind()
    if "config_site" not in set(sa.inspect(conn).get_table_names()):
        return
    conn.execute(
        sa.text(r"DELETE FROM config_site WHERE cle LIKE :motif ESCAPE '\'").bindparams(motif=MOTIF)
    )


def downgrade() -> None:
    #  Les plafonds retirés ne se reconstituent pas : vides, ils valaient
    #  « aucun plafond », ce que l'ancien code lit sans erreur.
    pass
