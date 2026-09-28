"""Les maintenances récurrentes du calendrier redeviennent réservées au conseil (#1428)

La 0212 (événements → affaires, #1092) a traduit les destinataires d'un
événement (`public_de`) pour ceux devenus ACTUALITÉ, et pour eux seuls. Un
événement suivi au kanban est devenu Entretien ou Étude & travaux sans
destinataires, et a perdu les deux restrictions que `evenement_visible`
appliquait :

- une maintenance récurrente ne se lisait que du conseil syndical (usage
  interne) : les contrats de maintenance, leurs fournisseurs, leurs pièces ;
- une AG ne se lisait que des copropriétaires.

Puis l'ouverture de l'affaire datée aux locataires (#1092, 25/09/2026) les a
mises sous leurs yeux — liste, fiche, pièces jointes, recherche. Signalé le
28/09/2026 : un locataire trouvait les contrats en cherchant « ag ».

La même décision (#1428) referme l'affaire datée aux locataires : l'AG
retrouve ainsi ses lecteurs d'avant — les copropriétaires — par la règle par
défaut, sans rien écrire. La maintenance récurrente, elle, était réservée au
conseil : la règle par défaut l'ouvrirait aux copropriétaires, contrats et
prix compris. Cette migration lui pose donc les Destinataires « Conseil
syndical » (#1343 : une affaire lit ceux que le conseil a choisis) — c'est
`public_de` de la 0212, appliqué à ce qu'elle a oublié.

⚠️ Une affaire dont le conseil a DÉJÀ choisi les destinataires n'est pas
touchée : son choix est plus récent que l'événement. Une affaire confidentielle
non plus — le conseil seul la lit déjà.

Idempotente : une affaire traitée porte des destinataires, et n'est plus
sélectionnée. `downgrade` ne rouvre rien — rendre à la copropriété un contrat
réservé au conseil n'est pas un retour arrière, c'est la fuite.

Revision ID: 0232
Revises: 0231
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "0232"
down_revision = "0231"
branch_labels = None
depends_on = None

#: Type de l'événement d'origine → Destinataires de l'affaire.
DESTINATAIRES = {
    "maintenance_recurrente": ["conseil_syndical"],
}


def upgrade() -> None:
    conn = op.get_bind()
    for type_evenement, codes in DESTINATAIRES.items():
        conn.execute(
            sa.text(
                "UPDATE ticket SET public_cible = :public "
                "WHERE categorie != :actualite "
                "AND COALESCE(confidentiel, 0) = 0 "
                "AND (public_cible IS NULL OR TRIM(public_cible) IN ('', '[]')) "
                "AND promu_depuis_evenement_id IN (SELECT id FROM evenement WHERE type = :type)"
            ).bindparams(
                public=json.dumps(codes, ensure_ascii=False),
                actualite="actualite",
                type=type_evenement,
            )
        )


def downgrade() -> None:
    pass
