"""L'Historique d'un événement de calendrier — la table qui manquait.

Demandé le 18/08/2026 : *« pour Calendrier il doit y avoir un historique et
workflow »*. Le **workflow existait déjà** sous un autre nom — les six colonnes
du Kanban répondent à la question de la section 3 du cadre #430, « où en est cet
objet ? ». Ce qui manquait était la **trace** : la colonne d'un événement
changeait sans que rien ne dise quand, par qui, ni pourquoi.

## Ce que cette migration NE fait pas, et c'est un arbitrage

Elle **ne touche pas au Kanban** — ni aux six colonnes, ni aux valeurs déjà
posées, ni au nom du champ. C'est la consigne reçue :

> « Ne modifie rien le kanban […], adapte à lui »

Un second champ d'état, aligné sur celui des tickets, aurait donné **deux
notions concurrentes** sur le même objet : celle du Kanban et celle du workflow.
Elles se contredisent au premier écart, et rien n'aurait dit laquelle fait foi.
Le Kanban EST le workflow d'un événement ; cette table en enregistre les
mouvements.

Revision ID: 0150
Revises: 0149
"""
import sqlalchemy as sa
from alembic import op

revision = "0150"
down_revision = "0149"
branch_labels = None
depends_on = None

TABLE = "evenement_evolution"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    #  Idempotente : la table est créée par `SQLModel.metadata.create_all` au
    #  démarrage si elle manque, et cette migration peut donc passer après elle.
    #  Sans ce garde, un redéploiement échouerait sur « table already exists » et
    #  `start.sh` (qui a `set -e`) laisserait le conteneur bloqué.
    if TABLE in _tables():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("evenement_id", sa.Integer(), sa.ForeignKey("evenement.id"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("contenu", sa.Text(), nullable=True),
        #  Les deux colonnes du Kanban, avant et après : renseignées pour un
        #  `etat`, nulles pour une correction. C'est leur absence qui empêche le
        #  fil de dessiner un jalon de suivi là où il n'y en a pas.
        sa.Column("ancien_statut", sa.String(), nullable=True),
        sa.Column("nouveau_statut", sa.String(), nullable=True),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("fichiers_urls", sa.Text(), nullable=False, server_default="[]"),
    )
    op.create_index(
        "ix_evenement_evolution_evenement_id", TABLE, ["evenement_id"]
    )


def downgrade() -> None:
    if TABLE not in _tables():
        return
    op.drop_index("ix_evenement_evolution_evenement_id", table_name=TABLE)
    op.drop_table(TABLE)
