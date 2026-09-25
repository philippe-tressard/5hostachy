"""Le troisième usage de l'assistant : sa configuration de départ (#1322)

La 0194 sème le prompt d'origine de chaque usage UNE fois : une installation qui
l'a déjà passée ne recevrait jamais celui de « Mise en forme des réponses par
courriel ». Cette migration le sème, et amorce l'usage comme la 0194 l'a fait
pour le second :

- le prompt d'origine (`reponse_courriel.CONSIGNE`, lu — jamais recopié) ;
- le modèle de l'usage « description », s'il est réglé : l'administrateur n'a
  qu'à confirmer ;
- **désactivé**. L'activer est un geste de l'administration, et c'est ce que la
  politique de confidentialité annonce (0223) : c'est la seule transmission à
  l'assistant qui se fait sans clic.

Rien n'est écrasé : une clé déjà présente reste telle quelle.

Revision ID: 0224
Revises: 0223
"""

import sqlalchemy as sa
from alembic import op

revision = "0224"
down_revision = "0223"
branch_labels = None
depends_on = None

USAGE = "reponse_courriel"


def _lire(conn, cle: str) -> str | None:
    ligne = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = :cle").bindparams(cle=cle)
    ).fetchone()
    return None if ligne is None else ligne[0]


def _poser_si_absent(conn, cle: str, valeur: str) -> None:
    if _lire(conn, cle) is None:
        conn.execute(
            sa.text("INSERT INTO config_site (cle, valeur) VALUES (:cle, :valeur)").bindparams(
                cle=cle, valeur=valeur
            )
        )


def upgrade() -> None:
    from app.utils.reponse_courriel import CONSIGNE

    conn = op.get_bind()
    _poser_si_absent(conn, f"llm_{USAGE}_prompt", CONSIGNE)
    modele = _lire(conn, "llm_description_modele")
    if modele:
        _poser_si_absent(conn, f"llm_{USAGE}_modele", modele)
    _poser_si_absent(conn, f"llm_{USAGE}_actif", "0")


def downgrade() -> None:
    conn = op.get_bind()
    for champ in ("prompt", "modele", "actif"):
        conn.execute(
            sa.text("DELETE FROM config_site WHERE cle = :cle").bindparams(
                cle=f"llm_{USAGE}_{champ}"
            )
        )
