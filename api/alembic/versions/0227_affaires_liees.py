"""Les affaires liées : une table de liens réciproques entre affaires (#1342)

Une ligne par paire, rangée (`affaire_id` < `liee_id`) : le lien vaut dans les
deux sens par construction. Idempotente : la table n'est créée que si elle
manque (une base neuve la reçoit déjà de `create_all`).

Revision ID: 0227
Revises: 0226
"""

import sqlalchemy as sa

from alembic import op

revision = "0227"
down_revision = "0226"
branch_labels = None
depends_on = None

TABLE = "affaire_liee"  # identifiant : constante du fichier


def upgrade() -> None:
    if TABLE in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("affaire_id", sa.Integer(), sa.ForeignKey("ticket.id"), nullable=False),
        sa.Column("liee_id", sa.Integer(), sa.ForeignKey("ticket.id"), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("cree_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
        sa.UniqueConstraint("affaire_id", "liee_id", name="uq_affaire_liee"),
    )
    op.create_index("ix_affaire_liee_affaire_id", TABLE, ["affaire_id"])
    op.create_index("ix_affaire_liee_liee_id", TABLE, ["liee_id"])


def downgrade() -> None:
    op.drop_table(TABLE)
