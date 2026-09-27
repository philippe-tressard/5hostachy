"""Le journal des appels à l'assistant IA (#1383)

Une ligne par appel : usage, fournisseur, modèle, jetons en entrée et en
sortie, durée, statut. Des compteurs, jamais de contenu — voir
`app/models/ia.py`. Idempotente : une base neuve reçoit déjà la table de
`create_all`.

Revision ID: 0230
Revises: 0229
"""

import sqlalchemy as sa

from alembic import op

revision = "0230"
down_revision = "0229"
branch_labels = None
depends_on = None

TABLE = "appel_ia"  # identifiant : constante du fichier


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("usage", sa.String(), nullable=False),
        sa.Column("fournisseur", sa.String(), nullable=False),
        sa.Column("modele", sa.String(), nullable=False),
        sa.Column("jetons_entree", sa.Integer(), nullable=True),
        sa.Column("jetons_sortie", sa.Integer(), nullable=True),
        sa.Column("duree_ms", sa.Integer(), nullable=False),
        sa.Column("statut", sa.String(), nullable=False),
    )
    op.create_index("ix_appel_ia_cree_le", TABLE, ["cree_le"])
    op.create_index("ix_appel_ia_usage", TABLE, ["usage"])


def downgrade() -> None:
    op.drop_table(TABLE)
