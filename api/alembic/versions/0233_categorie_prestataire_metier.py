"""La catégorie d'un prestataire dit son MÉTIER, plus le cadre d'une intervention (#1444)

« 🔄 Contrat récurrent » et « 🔧 Dépannage » étaient deux catégories de
prestataire. Elles ne décrivaient pas l'entreprise mais le CADRE d'une
intervention : Otis entretient l'ascenseur sous contrat ET le dépanne hors
contrat, et aucune des deux ne lui allait. « Sous contrat » se déduit désormais
des contrats actifs de la fiche.

Les deux valeurs sont fondues en `maintenance_depannage`. Les quatre autres
catégories (travaux, réglementaire, études & expertise, gestion) ne bougent pas.

⚠️ La colonne garde le `server_default` « ponctuel » que la 0053 lui a donné :
SQLite ne change pas le défaut d'une colonne sans recréer la table, et c'est le
genre d'opération qui bloque le conteneur au démarrage. L'application écrit
TOUJOURS la valeur (défaut du modèle et des schémas) — seul un `INSERT` SQL à la
main tomberait sur l'ancienne, et l'énumération la refuserait à la lecture.

`downgrade` rend `ponctuel` : l'ancienne distinction n'est pas reconstituable,
mais le code d'avant lit une valeur qu'il connaît.

Revision ID: 0233
Revises: 0232
"""

import sqlalchemy as sa
from alembic import op

revision = "0233"
down_revision = "0232"
branch_labels = None
depends_on = None

#: Ancienne valeur → nouvelle. Lue aussi par les tests : c'est elle qui dit
#: qu'une migration antérieure insérant `contrat_recurrent` (0156) reste juste.
CORRESPONDANCE = {
    "contrat_recurrent": "maintenance_depannage",
    "ponctuel": "maintenance_depannage",
}


def upgrade() -> None:
    conn = op.get_bind()
    for ancienne, nouvelle in CORRESPONDANCE.items():
        conn.execute(
            sa.text(
                "UPDATE prestataire SET type_prestataire = :nouvelle "
                "WHERE type_prestataire = :ancienne"
            ).bindparams(nouvelle=nouvelle, ancienne=ancienne)
        )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE prestataire SET type_prestataire = :ancienne "
            "WHERE type_prestataire = :nouvelle"
        ).bindparams(ancienne="ponctuel", nouvelle="maintenance_depannage")
    )
