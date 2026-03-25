"""vigik_import table + vigik.lot_id nullable

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ── 1. Vigik.lot_id → nullable (SQLite : recréation de table) ──────────
    columns = {c["name"]: c for c in inspector.get_columns("vigik")}
    if not columns.get("lot_id", {}).get("nullable", True):
        bind.execute(sa.text("""
            CREATE TABLE vigik_new (
                id      INTEGER PRIMARY KEY,
                code    VARCHAR NOT NULL,
                lot_id  INTEGER REFERENCES lot(id),
                user_id INTEGER NOT NULL REFERENCES utilisateur(id),
                statut  VARCHAR NOT NULL DEFAULT 'actif',
                cree_le DATETIME NOT NULL
            )
        """))
        bind.execute(sa.text("""
            INSERT INTO vigik_new
                SELECT id, code, lot_id, user_id, statut, cree_le
                FROM vigik
        """))
        bind.execute(sa.text("DROP TABLE vigik"))
        bind.execute(sa.text("ALTER TABLE vigik_new RENAME TO vigik"))

    # ── 2. Table vigik_import ───────────────────────────────────────────────
    tables = inspector.get_table_names()
    if "vigik_import" not in tables:
        op.create_table(
            "vigik_import",
            sa.Column("id",                    sa.Integer(),  primary_key=True, autoincrement=True),
            sa.Column("batiment_raw",          sa.String(),   nullable=True),
            sa.Column("appartement_raw",       sa.String(),   nullable=True),
            sa.Column("nom_proprietaire",      sa.String(),   nullable=False),
            sa.Column("nom_locataire",         sa.String(),   nullable=True),
            sa.Column("code",                  sa.String(),   nullable=True),
            sa.Column("statut",                sa.String(),   nullable=False, server_default="en_attente"),
            sa.Column("user_proprietaire_id",  sa.Integer(),  sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("user_locataire_id",     sa.Integer(),  sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("lot_id",                sa.Integer(),  sa.ForeignKey("lot.id"),          nullable=True),
            sa.Column("chez_locataire",        sa.Boolean(),  nullable=False, server_default="0"),
            sa.Column("refuse_par_locataire",  sa.Boolean(),  nullable=False, server_default="0"),
            sa.Column("vigik_id",              sa.Integer(),  sa.ForeignKey("vigik.id"),        nullable=True),
            sa.Column("notes_admin",           sa.Text(),     nullable=True),
            sa.Column("importe_le",            sa.DateTime(), nullable=False),
            sa.Column("resolu_le",             sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("vigik_import")

    # Remettre lot_id NOT NULL sur vigik
    bind = op.get_bind()
    bind.execute(sa.text("""
        CREATE TABLE vigik_new (
            id      INTEGER PRIMARY KEY,
            code    VARCHAR NOT NULL,
            lot_id  INTEGER NOT NULL REFERENCES lot(id),
            user_id INTEGER NOT NULL REFERENCES utilisateur(id),
            statut  VARCHAR NOT NULL DEFAULT 'actif',
            cree_le DATETIME NOT NULL
        )
    """))
    bind.execute(sa.text("""
        INSERT INTO vigik_new
            SELECT id, code, lot_id, user_id, statut, cree_le
            FROM vigik WHERE lot_id IS NOT NULL
    """))
    bind.execute(sa.text("DROP TABLE vigik"))
    bind.execute(sa.text("ALTER TABLE vigik_new RENAME TO vigik"))
