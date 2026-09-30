"""Les Entretiens fermés au conseil par la 0232 reviennent à la règle : les copropriétaires

Arbitré le 30/09/2026 : les Destinataires par défaut d'un Entretien sont les
copropriétaires, occupants et bailleurs (`DEFAUT_PAR_CATEGORIE`,
`app/utils/visibility/defauts_affaire.py`) — il était au conseil seul depuis
#1436. Les affaires restées au défaut s'y rangent d'elles-mêmes : la règle se
lit à chaque accès.

Restent celles que la 0232 avait adressées au conseil (« Conseil syndical »,
`public_cible = ["conseil_syndical"]`) : les maintenances récurrentes du
calendrier, promues en Entretien par la 0212. Ce n'était pas un choix du
conseil, c'était le défaut d'alors écrit en dur — l'utilisateur a demandé que
les affaires « affectées par défaut » suivent le nouveau. Leur choix est
effacé (`NULL`) : sans choix, c'est la règle de la catégorie qui décide.

⚠️ Ne touche QUE ces affaires-là, reconnues à trois signes réunis : catégorie
Entretien, promue d'une maintenance récurrente, Destinataires exactement
« Conseil syndical ». Un « Conseil syndical » posé à la main par le conseil —
avant #1436, ou sur un courriel transféré puis recatégorisé
(`courriel_transfert.PUBLIC_CONSEIL_SEUL`) — est un choix, et il tient.
`confidentiel` n'est pas touché : il referme encore.

Le JSON se lit en Python et non par comparaison de chaînes : une liste écrite
avec d'autres espaces serait passée à travers.

Idempotente : une affaire traitée n'a plus de destinataires, et n'est plus
sélectionnée. `downgrade` ne restaure RIEN, et c'est délibéré : les ids ne
sont conservés nulle part, et la 0232 se rejouerait sur une base où la règle
a changé.

Revision ID: 0243
Revises: 0242
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0243"
down_revision = "0242"
branch_labels = None
depends_on = None

CATEGORIE = "entretien"
#: Le type d'événement que la 0232 avait fermé au conseil — et lui seul.
TYPE_EVENEMENT = "maintenance_recurrente"
CONSEIL_SEUL = ["conseil_syndical"]


def _conseil_seul(brut) -> bool:
    try:
        codes = json.loads(brut)
    except (TypeError, ValueError):
        return False
    return isinstance(codes, list) and [str(c) for c in codes] == CONSEIL_SEUL


def upgrade() -> None:
    conn = op.get_bind()
    lignes = conn.execute(
        sa.text(
            "SELECT id, public_cible FROM ticket "
            "WHERE categorie = :categorie AND public_cible IS NOT NULL "
            "AND promu_depuis_evenement_id IN (SELECT id FROM evenement WHERE type = :type)"
        ).bindparams(categorie=CATEGORIE, type=TYPE_EVENEMENT)
    ).fetchall()
    ids = [i for i, brut in lignes if _conseil_seul(brut)]
    for tid in ids:
        conn.execute(sa.text("UPDATE ticket SET public_cible = NULL WHERE id = :id").bindparams(id=tid))
    #  Un nombre, jamais un identifiant ni un titre : ce que la MEP relit.
    print(f"0243 : {len(ids)} Entretien(s) rendu(s) aux copropriétaires")


def downgrade() -> None:
    pass
