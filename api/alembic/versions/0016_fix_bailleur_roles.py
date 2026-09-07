"""Retire le rôle 'résident' des copropriétaires bailleurs

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    bailleurs = conn.execute(
        sa.text(
            "SELECT id, roles_json FROM utilisateur WHERE statut = 'copropriétaire_bailleur'"
        )
    ).fetchall()

    for user in bailleurs:
        roles = [r.strip() for r in (user.roles_json or "").split(",") if r.strip()]
        cleaned = [r for r in roles if r != "résident"]
        if not cleaned:
            cleaned = ["propriétaire"]
        conn.execute(
            sa.text("UPDATE utilisateur SET roles_json = :rj, role = 'propriétaire' WHERE id = :id"),
            {"rj": ",".join(cleaned), "id": user.id},
        )


def downgrade():
    pass
