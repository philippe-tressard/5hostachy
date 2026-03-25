"""ticket_evolution

Revision ID: 0050
Revises: 0049
"""
from alembic import op
import sqlalchemy as sa

revision = "0050"
down_revision = "0049"


def upgrade():
    op.create_table(
        "ticket_evolution",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticket_id", sa.Integer, sa.ForeignKey("ticket.id"), nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("contenu", sa.String, nullable=True),
        sa.Column("ancien_statut", sa.String, nullable=True),
        sa.Column("nouveau_statut", sa.String, nullable=True),
        sa.Column("auteur_id", sa.Integer, sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("cree_le", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("ticket_evolution")
