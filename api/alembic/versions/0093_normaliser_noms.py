"""Normalise prenom (Title Case) et nom (UPPER) des utilisateurs existants.

Revision ID: 0093
Revises: 0092
Create Date: 2026-04-14
"""
from alembic import op
from sqlalchemy import text

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None


def upgrade():
    # SQLite n'a pas INITCAP — on utilise UPPER pour nom et Python pour prenom (title case)
    conn = op.get_bind()

    # 1. nom → UPPER (SQLite supporte UPPER + TRIM)
    conn.execute(text("UPDATE utilisateur SET nom = UPPER(TRIM(nom))"))
    conn.execute(text("UPDATE utilisateur SET nom_aide = UPPER(TRIM(nom_aide)) WHERE nom_aide IS NOT NULL"))
    conn.execute(text("UPDATE utilisateur SET nom_proprietaire = UPPER(TRIM(nom_proprietaire)) WHERE nom_proprietaire IS NOT NULL"))

    # 2. prenom → Title Case (Python, car SQLite n'a pas INITCAP)
    rows = conn.execute(text("SELECT id, prenom FROM utilisateur WHERE prenom IS NOT NULL")).fetchall()
    for row in rows:
        conn.execute(text("UPDATE utilisateur SET prenom = :p WHERE id = :id"), {"p": row[1].strip().title(), "id": row[0]})

    rows_aide = conn.execute(text("SELECT id, prenom_aide FROM utilisateur WHERE prenom_aide IS NOT NULL")).fetchall()
    for row in rows_aide:
        conn.execute(text("UPDATE utilisateur SET prenom_aide = :p WHERE id = :id"), {"p": row[1].strip().title(), "id": row[0]})


def downgrade():
    pass
