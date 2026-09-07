"""Ajout de la valeur 'annulé' à l'enum StatutTicket

Revision ID: 0051
Revises: 0050
"""
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite stocke les enums comme VARCHAR → rien à faire.
    # PostgreSQL nécessite d'ajouter la valeur à l'enum natif.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE statutticket ADD VALUE IF NOT EXISTS 'annulé'")


def downgrade() -> None:
    pass
