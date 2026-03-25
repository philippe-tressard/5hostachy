"""lot_id nullable sur telecommande

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # SQLite ne supporte pas ALTER COLUMN directement.
    # On recrée la table avec lot_id nullable.
    inspector = sa.inspect(bind)
    columns = {c["name"]: c for c in inspector.get_columns("telecommande")}

    # Si lot_id est déjà nullable, rien à faire
    if columns.get("lot_id", {}).get("nullable", False):
        return

    bind.execute(sa.text("""
        CREATE TABLE telecommande_new (
            id          INTEGER PRIMARY KEY,
            code        VARCHAR NOT NULL,
            lot_id      INTEGER REFERENCES lot(id),
            user_id     INTEGER NOT NULL REFERENCES utilisateur(id),
            statut      VARCHAR NOT NULL DEFAULT 'actif',
            chez_locataire BOOLEAN NOT NULL DEFAULT 0,
            cree_le     DATETIME NOT NULL
        )
    """))
    bind.execute(sa.text("""
        INSERT INTO telecommande_new
            SELECT id, code, lot_id, user_id, statut, chez_locataire, cree_le
            FROM telecommande
    """))
    bind.execute(sa.text("DROP TABLE telecommande"))
    bind.execute(sa.text("ALTER TABLE telecommande_new RENAME TO telecommande"))


def downgrade() -> None:
    # Remettre lot_id NOT NULL (les lignes sans lot_id seront perdues)
    bind = op.get_bind()
    bind.execute(sa.text("""
        CREATE TABLE telecommande_new (
            id          INTEGER PRIMARY KEY,
            code        VARCHAR NOT NULL,
            lot_id      INTEGER NOT NULL REFERENCES lot(id),
            user_id     INTEGER NOT NULL REFERENCES utilisateur(id),
            statut      VARCHAR NOT NULL DEFAULT 'actif',
            chez_locataire BOOLEAN NOT NULL DEFAULT 0,
            cree_le     DATETIME NOT NULL
        )
    """))
    bind.execute(sa.text("""
        INSERT INTO telecommande_new
            SELECT id, code, lot_id, user_id, statut, chez_locataire, cree_le
            FROM telecommande WHERE lot_id IS NOT NULL
    """))
    bind.execute(sa.text("DROP TABLE telecommande"))
    bind.execute(sa.text("ALTER TABLE telecommande_new RENAME TO telecommande"))
