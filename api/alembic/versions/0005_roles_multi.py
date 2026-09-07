"""Ajout colonne roles_json sur la table utilisateur (multi-rôles cumulables)

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    cols = [c["name"] for c in inspector.get_columns("utilisateur")]
    if "roles_json" not in cols:
        op.add_column(
            "utilisateur",
            sa.Column("roles_json", sa.String(), nullable=False, server_default=""),
        )

    # Initialiser roles_json à partir du champ role existant pour tous les users
    op.execute(
        "UPDATE utilisateur SET roles_json = role WHERE roles_json = '' OR roles_json IS NULL"
    )


def downgrade() -> None:
    op.drop_column("utilisateur", "roles_json")
