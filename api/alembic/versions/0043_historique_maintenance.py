"""Crée la table historique_maintenance pour le suivi des exécutions cron."""

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "historique_maintenance",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("declenchee_par", sa.String(), nullable=False, server_default="cron"),
        sa.Column("statut", sa.String(), nullable=False, server_default="succes"),
        sa.Column("tokens_supprimes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("taille_db_octets", sa.Integer(), nullable=True),
        sa.Column("duree_secondes", sa.Integer(), nullable=True),
        sa.Column("erreur", sa.Text(), nullable=True),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("terminee_le", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("historique_maintenance")
