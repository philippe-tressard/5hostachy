"""La politique dit ce que la synthèse transmet d'autres affaires (#1647, 04/10/2026)

La synthèse d'une affaire close nomme, à l'assistant, les autres affaires
résolues sur le même équipement et le même périmètre en 24 mois : leur numéro
et leur date de clôture, jamais leur contenu. La politique de confidentialité
énumère ce qui part au service de modèle de langage : elle doit le dire.

Cette migration insère la clause (`SYNTHESE_RECIDIVE`, lue dans le seed —
jamais recopiée) dans la phrase de la synthèse d'une affaire close, juste après
« les personnes désignées par leur rôle ». Aucune table, aucune colonne.

Idempotente : une base neuve reçoit déjà la clause par la 0255 (qui lit le seed) ;
une phrase reformulée depuis l'administration n'est pas touchée.

Revision ID: 0257
Revises: 0256
"""

import sqlalchemy as sa

from alembic import op

revision = "0257"
down_revision = "0256"
branch_labels = None
depends_on = None

POLITIQUE = "politique_confidentialite"
#: Le passage tel que la 0255 l'a posé, avant la clause — recopié ICI parce que
#: c'est précisément ce que cette migration remplace (le seed ne le porte plus).
AVANT = "les personnes désignées par leur rôle, sont transmis pour en rédiger un bilan"


def _passage(clause: str) -> str:
    return f"les personnes désignées par leur rôle{clause}, sont transmis pour en rédiger un bilan"


def _poser_la_clause(sens: int) -> None:
    from app.seed.contenus_legaux import SYNTHESE_RECIDIVE
    from app.utils.textes_livres import remplacer_passage

    conn = op.get_bind()
    if "config_site" not in set(sa.inspect(conn).get_table_names()):
        return
    avant, apres = (AVANT, _passage(SYNTHESE_RECIDIVE))
    if sens < 0:
        avant, apres = apres, avant
    remplacer_passage(conn, "config_site", {"cle": POLITIQUE}, "valeur", avant, apres)


def upgrade() -> None:
    _poser_la_clause(+1)


def downgrade() -> None:
    _poser_la_clause(-1)
