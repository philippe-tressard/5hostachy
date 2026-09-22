"""La date de fin de validité n'est plus saisie — elle se déduit (#1093).

## L'arbitrage, pris à l'écran le 22/09/2026

> « Visible jusqu'au (dans QUAND) ne doit pas être demandé à l'utilisateur.
>   Cette date est à enlever. Elle est calculée par l'appli. »

La migration **0204**, livrée le matin même en v2.11.0, avait ajouté cette
colonne pour la troisième famille d'actualités — « à durée de vie choisie ».
Cette famille est **supprimée** : il n'en reste que deux, et aucune ne demande
quoi que ce soit.

    perime_le =  fin de l'événement    si date d'événement
          sinon  jamais

Ce qui n'a pas de date d'événement ne périme pas — et n'en a pas besoin :
l'archivage automatique à trente jours (`ARCHIVAGE_DELAI_JOURS`) couvre déjà ce
cas depuis le 19/08/2026, pour les sept objets du site. Le champ faisait donc
saisir ce que le produit savait déjà décider.

## 🔴 Pourquoi retirer la colonne plutôt que la laisser dormir

Une colonne que plus rien ne remplit est exactement ce que le cadre #430
interdit — et c'est le défaut que `Ticket.echeance` incarne déjà dans ce dépôt :
écrite par un routeur, relue par personne, et gardée « au cas où ». Elle a
survécu assez longtemps pour qu'un champ d'écran la promette à l'utilisateur.

Ici, la colonne a moins d'une heure de production et pas une ligne renseignée :
la retirer coûte une migration, la garder coûterait une explication à chaque
lecture du modèle. `downgrade` la remet si besoin.

⚠️ 0204 n'est PAS modifiée — une migration appliquée ne se modifie jamais. La
chaîne dit donc l'histoire exacte : la colonne a existé une demi-journée.
"""
import sqlalchemy as sa
from alembic import op

revision = "0205"
down_revision = "0204"
branch_labels = None
depends_on = None

#: L'identifiant ne peut pas se lier en SQLite : il vient de cette constante.
TABLE = "publication"
COLONNE = "visible_jusqu_au"


def _colonnes_existantes(conn, table: str) -> set[str]:
    """L'inspecteur plutôt qu'un `PRAGMA` en f-string (cf. 0204)."""
    return {colonne["name"] for colonne in sa.inspect(conn).get_columns(table)}


def upgrade():
    conn = op.get_bind()
    if COLONNE not in _colonnes_existantes(conn, TABLE):
        return
    with op.batch_alter_table(TABLE) as lot:
        lot.drop_column(COLONNE)


def downgrade():
    op.add_column(TABLE, sa.Column(COLONNE, sa.Date(), nullable=True))
