"""`reponse_relance` — les réponses du syndic à une relance, CONSERVÉES

## Le défaut que cette table corrige

La v3.79.0 captait la réponse du syndic à une relance groupée et prévenait le
conseil syndical par une notification portant le texte. Elle répondait donc à
« le conseil est-il prévenu ? » — et pas à « où le relit-on ? ».

Une notification se lit une fois, puis descend dans la pile. Passé quelques
jours, la réponse était en base, dans un champ `corps`, et introuvable.

🔴 C'est le défaut même que ce chantier prétendait corriger : *« une réponse
arrive et personne ne la voit »*. Il avait été déplacé de la boîte aux lettres
vers une table de notifications, ce qui n'est pas la même chose que le résoudre.
Relevé à l'écran le 04/09/2026 : *« où sera affiché le retour syndic ? »*.

## Plusieurs réponses par relance

Le jeton ne s'épuise pas : le syndic peut répondre un dossier à la fois, ou
préciser le lendemain. Chaque réponse est une LIGNE — jamais un écrasement de la
précédente, qui perdrait ce qu'on vient de sauver.

## Aucune contrainte de clé étrangère

`relance_id` n'est pas déclaré `ForeignKey` : SQLite refuse d'altérer les
contraintes d'une table existante, et une migration qui crasherait APRÈS avoir
créé la table bloquerait le conteneur au démarrage (`start.sh` a `set -e`).
C'est arrivé deux fois — 0117 et 0165. L'index suffit à la recherche.

Revision ID: 0174
Revises: 0173
Create Date: 2026-09-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0174"
down_revision = "0173"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade():
    if "reponse_relance" in _tables():
        return
    op.create_table(
        "reponse_relance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("relance_id", sa.Integer(), nullable=False),
        sa.Column("expediteur", sa.String(), nullable=False, server_default=""),
        sa.Column("contenu", sa.String(), nullable=False, server_default=""),
        sa.Column("recue_le", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_reponse_relance_relance_id", "reponse_relance", ["relance_id"])


def downgrade():
    if "reponse_relance" in _tables():
        op.drop_index("ix_reponse_relance_relance_id", table_name="reponse_relance")
        op.drop_table("reponse_relance")
