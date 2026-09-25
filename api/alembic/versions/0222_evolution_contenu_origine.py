"""Le texte REÇU d'une réponse par courriel, à côté de sa mise en forme (#1322)

Quand l'assistant met en forme la réponse du syndic reçue par courriel, la Suite
porte la version mise en forme dans `contenu`, et le texte reçu dans
`contenu_origine` — l'écran l'offre sous « Message d'origine », pour qu'une
déformation par le modèle se voie.

La colonne est posée sur les trois fils (`EvolutionMixin`) : ils se lisent
pareil, et `TicketEvolution` vit dans `core.py`, gelé par le contrôle de
modularité. Nullable, sans défaut : toutes les entrées existantes n'ont rien
reçu par courriel à conserver. Aucune clé étrangère (interdite dans un
`add_column` SQLite, cf. CLAUDE.md).

Revision ID: 0222
Revises: 0221
"""

import sqlalchemy as sa

from alembic import op

revision = "0222"
down_revision = "0221"
branch_labels = None
depends_on = None

#: Identifiants : constantes du fichier, jamais des valeurs liées.
TABLES = ("ticket_evolution", "publication_evolution", "evenement_evolution")
COLONNE = "contenu_origine"


def upgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    existantes = set(inspecteur.get_table_names())
    for table in TABLES:
        if table not in existantes:
            continue
        if COLONNE in {c["name"] for c in inspecteur.get_columns(table)}:
            continue
        op.add_column(table, sa.Column(COLONNE, sa.Text(), nullable=True))


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as lot:
            lot.drop_column(COLONNE)
