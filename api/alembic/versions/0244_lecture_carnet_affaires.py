"""Carnet = Affaires = Kanban : les affaires restées au défaut d'hier suivent le standard

Arbitré le 30/09/2026 (« ne t'écarte pas de ce nouveau standard ») : sans choix
du conseil, une Panne se lit de tous les copropriétaires et des locataires de
son périmètre, un Entretien de tous les copropriétaires de la résidence, une
Étude & travaux du conseil seul puis des copropriétaires dès l'AG
(`app/utils/visibility/defauts_affaire.py`). Une affaire SANS destinataires
suit la règle d'elle-même : elle se lit à chaque accès.

Restent celles qui portent, écrit en dur, le DÉFAUT D'HIER — l'utilisateur a
demandé que les affaires « affectées par défaut » soient corrigées :

* une Panne aux « Copropriétaires occupants + Locataires » : le défaut d'une
  Panne dans un bâtiment depuis #1343. Un conseil qui les choisissait les
  voyait ramenés à « aucun choix » par le formulaire (`SectionDestinataires`,
  `choisir`) : une telle liste stockée n'est donc pas un choix ;
* un Entretien aux « Copropriétaires » (occupants + bailleurs, ou l'ancien
  code `copropriétaires`) : le défaut d'Entretien, mais lu dans le périmètre
  seulement — le standard l'ouvre à toute la résidence.

Leur liste est effacée (`NULL`) : sans choix, la catégorie décide.

⚠️ Ne touche RIEN d'autre :
- une Étude & travaux : la 0236 les a toutes ramenées au défaut ; celles qui
  portent des destinataires ont été choisies depuis, ou créées par un
  transfert de courriels (`courriel_transfert.PUBLIC_CONSEIL_SEUL`, « choisi
  et non hérité ») — un fil de courriels privés reste au conseil ;
- « Tous » sur une Panne : plus large que le standard, c'est un choix ;
- `confidentiel` : il referme encore.

Le JSON se lit en Python, jamais par comparaison de chaînes (ordre et espaces).
Idempotente : une affaire traitée n'a plus de destinataires. `downgrade` ne
restaure rien : les ids ne sont conservés nulle part.

Revision ID: 0244
Revises: 0243
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0244"
down_revision = "0243"
branch_labels = None
depends_on = None

#: Catégorie → les listes qui sont le défaut d'hier, pas un choix.
DEFAUTS_D_HIER = {
    "panne": [{"copropriétaires_occupants", "locataires"}],
    "entretien": [{"copropriétaires_occupants", "bailleurs"}, {"copropriétaires"}],
}


def _defaut_d_hier(categorie: str, brut) -> bool:
    try:
        codes = json.loads(brut)
    except (TypeError, ValueError):
        return False
    if not isinstance(codes, list):
        return False
    return {str(c) for c in codes} in DEFAUTS_D_HIER.get(categorie, [])


def upgrade() -> None:
    conn = op.get_bind()
    for categorie in DEFAUTS_D_HIER:
        lignes = conn.execute(
            sa.text(
                "SELECT id, public_cible FROM ticket "
                "WHERE categorie = :categorie AND public_cible IS NOT NULL"
            ).bindparams(categorie=categorie)
        ).fetchall()
        ids = [i for i, brut in lignes if _defaut_d_hier(categorie, brut)]
        for tid in ids:
            conn.execute(
                sa.text("UPDATE ticket SET public_cible = NULL WHERE id = :id").bindparams(id=tid)
            )
        #  Un nombre, jamais un identifiant ni un titre : ce que la MEP relit.
        print(f"0244 : {len(ids)} {categorie}(s) rendue(s) au standard de lecture")


def downgrade() -> None:
    pass
