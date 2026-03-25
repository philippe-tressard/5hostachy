"""Création table petite_annonce

Revision ID: 0069
Revises: 0068
Create Date: 2026-03-21
"""
from alembic import op

revision = '0069'
down_revision = '0068'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS petite_annonce (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titre TEXT NOT NULL,
            description TEXT NOT NULL,
            type_annonce TEXT NOT NULL DEFAULT 'vente',
            categorie TEXT NOT NULL DEFAULT 'divers',
            prix REAL,
            negotiable BOOLEAN NOT NULL DEFAULT 0,
            photos_json TEXT NOT NULL DEFAULT '[]',
            statut TEXT NOT NULL DEFAULT 'disponible',
            contact_visible BOOLEAN NOT NULL DEFAULT 1,
            auteur_id INTEGER NOT NULL REFERENCES utilisateur(id),
            cree_le DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            mis_a_jour_le DATETIME
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS petite_annonce")
