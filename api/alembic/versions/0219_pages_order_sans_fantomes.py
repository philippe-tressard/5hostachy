"""L'ordre du menu servi ne cite plus de pages disparues (#1114)

`pages_order` (clé de `config_site`, réordonnée depuis l'administration) portait
au 24/09/2026 trois identifiants qui ne désignent plus aucune page :

| identifiant | disparu le | devenu |
|---|---|---|
| `acces-badges` | 12/09/2026 (#928) | un onglet de « Mes lots & accès » |
| `actualites` | 23/09/2026 (v2.0.0, #1091) | le filtre Actualité d'Affaires |
| `calendrier` | 23/09/2026 (v2.0.0, #1092) | le filtre Calendrier d'Affaires |

Le menu les écartait en silence (`ordonnerPages`) : sans effet visible, mais
une donnée sale que la sonde du point 20 signale désormais. Cette migration les
retire, et eux seuls — la liste est FIGÉE ici : une migration ne sait pas quelles
pages le code connaîtra demain, et ne doit rien retirer d'autre.

Idempotente : rien à retirer, rien n'est écrit. Le downgrade ne les remet pas :
un identifiant sans page n'a aucun sens à restaurer.

Revision ID: 0219
Revises: 0218
"""
import json

from sqlalchemy import text

from alembic import op

revision = "0219"
down_revision = "0218"
branch_labels = None
depends_on = None

#: Pages disparues, avec leur date — figées : c'est de l'historique.
IDS_RETIRES = ("acces-badges", "actualites", "calendrier")


def upgrade() -> None:
    lien = op.get_bind()
    valeur = lien.execute(
        text("SELECT valeur FROM config_site WHERE cle = 'pages_order'")
    ).scalar()
    if not valeur:
        return
    try:
        ordre = json.loads(valeur)
    except ValueError:
        #  Une valeur illisible n'est pas à « réparer » à l'aveugle : la sonde du
        #  point 20 la rapporte INCONNU, et c'est à l'administration de trancher.
        return
    if not isinstance(ordre, list):
        return
    nettoye = [i for i in ordre if i not in IDS_RETIRES]
    if nettoye != ordre:
        lien.execute(
            text("UPDATE config_site SET valeur = :v WHERE cle = 'pages_order'").bindparams(
                v=json.dumps(nettoye)
            )
        )


def downgrade() -> None:
    pass
