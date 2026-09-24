"""Deux phrases fausses servies par les textes légaux — corrigées dans la base

## 1. La politique de confidentialité niait une purge qui existe (#1073)

Elle disait, depuis la 0199 : « Historique des envois de courriels : conservé
pour le suivi des notifications. **Aucune purge automatique n'est en place à ce
jour** ». C'était faux : l'historique est purgé à 90 jours chaque dimanche
(`utils.maintenance.purger`, appelée par `maintenance.sh` depuis #1232). Le
relevé du 20/09 qui avait conclu à son absence cherchait le nom du modèle,
`HistoriqueEmail`, et non celui de la table, `historique_email`.

La nouvelle phrase est LUE dans le seed (`CONSERVATION_COURRIELS`), jamais
recopiée ici — même règle que la 0199 : deux rédactions d'un texte juridique
divergeraient. L'ancienne, elle, est écrite ici en dur : c'est un fait passé,
elle ne changera plus.

## 2. Les mentions légales menaient à une page 404 (#1070)

La 0170 a écrit `href="/politique-confidentialite"` ; la route est
`/politique-de-confidentialite`. Mesuré en production le 24/09/2026 : 404.

## Idempotence, et ce qui n'est jamais écrasé

Chaque correction est un remplacement EXACT : si l'ancien texte n'est plus là —
rédaction faite depuis Admin → Légal, ou migration déjà passée —, rien n'est
touché. Le downgrade fait le remplacement inverse, et lui seul.

Revision ID: 0218
Revises: 0217
"""
from sqlalchemy import text

from alembic import op

revision = "0218"
down_revision = "0217"
branch_labels = None
depends_on = None

#: Le texte exact posé par la 0199 (lu alors dans `AJOUTS_1034`).
ANCIENNE_CONSERVATION = (
    "<li>Historique des envois de courriels\xa0: conservé pour le suivi des "
    "notifications. <strong>Aucune purge automatique n'est en place à ce jour"
    "</strong>\xa0; l'effacement s'obtient sur demande à l'adresse du point\xa01."
)
LIEN_MORT = 'href="/politique-confidentialite"'
LIEN_JUSTE = 'href="/politique-de-confidentialite"'


def _nouvelle_conservation() -> str:
    """La phrase juste, lue dans le seed — jamais recopiée ici."""
    from app.seed.contenus_legaux import CONSERVATION_COURRIELS

    return CONSERVATION_COURRIELS


def _remplacer(cle: str, avant: str, apres: str) -> None:
    lien = op.get_bind()
    ligne = lien.execute(
        text("SELECT valeur FROM config_site WHERE cle = :c").bindparams(c=cle)
    ).fetchone()
    #  Rien en base : le seed sert de repli, et il est déjà juste.
    if ligne is None or avant not in (ligne[0] or ""):
        return
    lien.execute(
        text("UPDATE config_site SET valeur = :v WHERE cle = :c").bindparams(
            v=ligne[0].replace(avant, apres), c=cle
        )
    )


def upgrade() -> None:
    _remplacer("politique_confidentialite", ANCIENNE_CONSERVATION, _nouvelle_conservation())
    _remplacer("mentions_legales", LIEN_MORT, LIEN_JUSTE)


def downgrade() -> None:
    #  Le lien n'est PAS remis en 404 : `LIEN_JUSTE` peut figurer ailleurs dans le
    #  texte, et le remplacer partout casserait des liens qui l'étaient déjà.
    _remplacer("politique_confidentialite", _nouvelle_conservation(), ANCIENNE_CONSERVATION)
