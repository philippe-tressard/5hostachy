"""`evenement.contrat_id` — rapprocher une visite de sa SOURCE, plus de son titre

#605, point 2. Le pré-remplissage du kanban reconnaît une visite déjà créée par
son **titre littéral + le mois**. Deux fragilités, toutes deux réelles :

- **le titre** : renommer un contrat, ou renommer le prestataire, fait perdre la
  correspondance et **recrée tout l'exercice en double** ;
- **le mois** : passer la fréquence de 2 à 3 par an déplace les visites. Les
  anciennes ne correspondent plus, et l'on obtient 3 nouvelles **en plus** des 2
  existantes.

Une chaîne d'affichage n'est pas une identité. `contrat_id` en est une.

## Pourquoi la colonne est NULLABLE, et le restera

1. les visites **déjà créées** n'en ont pas, et il n'y a aucun moyen fiable de
   les rattacher après coup — c'est précisément parce que le titre ne suffit pas
   qu'on ajoute cette colonne. Elles continuent d'être reconnues par leur titre :
   le front garde les deux clés, sans quoi le premier clic après cette migration
   recréerait l'intégralité de l'exercice, c'est-à-dire le défaut qu'on corrige ;
2. un événement de maintenance **saisi à la main** n'a pas de contrat, et c'est
   légitime.

⚠️ `ondelete` n'est pas posé : SQLite ne réécrit pas une contrainte sans
recréer la table, et le comportement voulu — un contrat supprimé laisse ses
visites passées — est celui d'une FK nullable non contrainte. Les suppressions de
contrat passent par `purge_referentielle`, qui lit les métadonnées.

Revision ID: 0165
Revises: 0164
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0165"
down_revision = "0164"
branch_labels = None
depends_on = None


def _colonnes(nom_table: str) -> set[str]:
    """Les colonnes présentes — la migration doit pouvoir se rejouer.

    ⚠️ `add_column` sur une colonne existante lève, et `start.sh` a `set -e` :
    un conteneur bloqué au démarrage. Le dépôt a déjà payé ce défaut.
    """
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(nom_table)}


def upgrade():
    if "contrat_id" not in _colonnes("evenement"):
        op.add_column(
            "evenement",
            sa.Column("contrat_id", sa.Integer(), sa.ForeignKey("contrat_entretien.id"), nullable=True),
        )


def downgrade():
    if "contrat_id" in _colonnes("evenement"):
        op.drop_column("evenement", "contrat_id")
