"""L'affaire porte son intervenant et, pour un Entretien, sa récurrence (#1092, lot 5).

Les événements du calendrier deviennent des affaires (arbitré le 23/09/2026).
Seize d'entre eux portent un prestataire, et une maintenance récurrente sa
fréquence : trois colonnes qu'une affaire n'avait pas.

- `prestataire_id` : la section « Intervenant » du cadre, construite par ce lot.
- `frequence_type` / `frequence_valeur` : « tous les N mois », pour la seule
  catégorie Entretien — mêmes noms et mêmes valeurs que `Evenement` et
  `ContratEntretien`, pour que la recopie soit littérale.

Colonnes simples, **sans clé étrangère** : SQLite refuse d'altérer les
contraintes d'une table existante (0117, 0165 — le conteneur s'arrêtait).
"""
import sqlalchemy as sa
from alembic import op

revision = "0211"
down_revision = "0210"
branch_labels = None
depends_on = None

TABLE = "ticket"
#  Identifiants de colonnes : constantes de ce fichier, jamais une saisie.
COLONNES = (
    ("prestataire_id", sa.Integer()),
    ("frequence_type", sa.String()),
    ("frequence_valeur", sa.Integer()),
)


def _colonnes(conn) -> set[str]:
    return {c["name"] for c in sa.inspect(conn).get_columns(TABLE)}


def upgrade():
    existantes = _colonnes(op.get_bind())
    for nom, type_ in COLONNES:
        if nom not in existantes:
            op.add_column(TABLE, sa.Column(nom, type_, nullable=True))


def downgrade():
    existantes = _colonnes(op.get_bind())
    with op.batch_alter_table(TABLE) as lot:
        for nom, _ in COLONNES:
            if nom in existantes:
                lot.drop_column(nom)
