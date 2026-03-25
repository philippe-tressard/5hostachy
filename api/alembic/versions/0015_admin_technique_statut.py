"""Ajout statut admin_technique et mise à jour de l'utilisateur admin initial

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # SQLite ne supporte pas ALTER COLUMN sur enum — la contrainte est applicative,
    # on met simplement à jour le statut et les rôles de l'admin technique.
    conn.execute(
        sa.text(
            """
            UPDATE utilisateur
            SET statut    = 'admin_technique',
                role      = 'admin',
                roles_json = 'admin'
            WHERE email = 'admin@localhost'
            """
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE utilisateur
            SET statut = 'copropriétaire_résident'
            WHERE email = 'admin@localhost'
              AND statut = 'admin_technique'
            """
        )
    )
