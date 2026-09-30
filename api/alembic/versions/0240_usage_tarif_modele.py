"""Le quatrième usage de l'assistant : « Tarif d'un modèle » (30/09/2026)

Même geste que la 0224 pour le troisième usage : un prompt d'origine ne parvient
à une installation en service que par une migration. Celle-ci sème :

- le prompt d'origine (`tarif_modele.CONSIGNE`, lu — jamais recopié) ;
- le modèle de l'usage « description », s'il est réglé ;
- l'activation, **seulement si ce modèle a pu être repris**. À la différence
  de la 0224, rien ne part sans un clic de l'administrateur, et seuls le nom
  du fournisseur, celui d'un modèle et une grille publique sont transmis :
  l'usage n'a aucune raison d'attendre un second geste pour servir.

Rien n'est écrasé : une clé déjà présente reste telle quelle.

Revision ID: 0240
Revises: 0239
"""

import sqlalchemy as sa
from alembic import op

revision = "0240"
down_revision = "0239"
branch_labels = None
depends_on = None

USAGE = "tarif_modele"


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
    from app.utils.tarif_modele import CONSIGNE

    conn = op.get_bind()
    _poser_si_absent(conn, f"llm_{USAGE}_prompt", CONSIGNE)
    modele = _lire(conn, "llm_description_modele")
    if modele:
        _poser_si_absent(conn, f"llm_{USAGE}_modele", modele)
    _poser_si_absent(conn, f"llm_{USAGE}_actif", "1" if modele else "0")


def downgrade() -> None:
    conn = op.get_bind()
    for champ in ("prompt", "modele", "actif"):
        conn.execute(
            sa.text("DELETE FROM config_site WHERE cle = :cle").bindparams(
                cle=f"llm_{USAGE}_{champ}"
            )
        )
