"""lot_import.batiment_id : rendre nullable (parking sans bâtiment)

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Vérifier si la colonne est déjà nullable (éviter une double exécution)
    cols = {c["name"]: c for c in inspector.get_columns("lot_import")}
    if cols.get("batiment_id", {}).get("nullable", True):
        return  # déjà nullable, rien à faire

    # SQLite ne supporte pas ALTER COLUMN : recréer la table
    # 1. Renommer l'ancienne table
    op.execute("ALTER TABLE lot_import RENAME TO _lot_import_old")

    # 2. Créer la nouvelle table avec batiment_id nullable
    op.create_table(
        "lot_import",
        sa.Column("id",                  sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("batiment_id",         sa.Integer(),  sa.ForeignKey("batiment.id"), nullable=True),
        sa.Column("numero",              sa.String(),   nullable=False),
        sa.Column("type_raw",            sa.String(),   nullable=False),
        sa.Column("etage_raw",           sa.String(),   nullable=True),
        sa.Column("no_coproprietaire",   sa.String(),   nullable=True),
        sa.Column("nom_coproprietaire",  sa.String(),   nullable=True),
        sa.Column("statut",              sa.String(),   nullable=False, server_default="en_attente"),
        sa.Column("lot_id",              sa.Integer(),  sa.ForeignKey("lot.id"),      nullable=True),
        sa.Column("utilisateurs_json",   sa.String(),   nullable=False, server_default="[]"),
        sa.Column("notes_admin",         sa.Text(),     nullable=True),
        sa.Column("importe_le",          sa.DateTime(), nullable=False),
        sa.Column("resolu_le",           sa.DateTime(), nullable=True),
    )

    # 3. Copier les données
    op.execute("""
        INSERT INTO lot_import
            (id, batiment_id, numero, type_raw, etage_raw,
             no_coproprietaire, nom_coproprietaire, statut,
             lot_id, utilisateurs_json, notes_admin, importe_le, resolu_le)
        SELECT
            id, batiment_id, numero, type_raw, etage_raw,
            no_coproprietaire, nom_coproprietaire, statut,
            lot_id, utilisateurs_json, notes_admin, importe_le, resolu_le
        FROM _lot_import_old
    """)

    # 4. Supprimer l'ancienne table
    op.execute("DROP TABLE _lot_import_old")


def downgrade() -> None:
    # Recréer avec NOT NULL (en forçant 0 pour les NULL)
    op.execute("ALTER TABLE lot_import RENAME TO _lot_import_old")
    op.create_table(
        "lot_import",
        sa.Column("id",                  sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("batiment_id",         sa.Integer(),  sa.ForeignKey("batiment.id"), nullable=False),
        sa.Column("numero",              sa.String(),   nullable=False),
        sa.Column("type_raw",            sa.String(),   nullable=False),
        sa.Column("etage_raw",           sa.String(),   nullable=True),
        sa.Column("no_coproprietaire",   sa.String(),   nullable=True),
        sa.Column("nom_coproprietaire",  sa.String(),   nullable=True),
        sa.Column("statut",              sa.String(),   nullable=False, server_default="en_attente"),
        sa.Column("lot_id",              sa.Integer(),  sa.ForeignKey("lot.id"),      nullable=True),
        sa.Column("utilisateurs_json",   sa.String(),   nullable=False, server_default="[]"),
        sa.Column("notes_admin",         sa.Text(),     nullable=True),
        sa.Column("importe_le",          sa.DateTime(), nullable=False),
        sa.Column("resolu_le",           sa.DateTime(), nullable=True),
    )
    op.execute("""
        INSERT INTO lot_import
            (id, batiment_id, numero, type_raw, etage_raw,
             no_coproprietaire, nom_coproprietaire, statut,
             lot_id, utilisateurs_json, notes_admin, importe_le, resolu_le)
        SELECT
            id, COALESCE(batiment_id, 0), numero, type_raw, etage_raw,
            no_coproprietaire, nom_coproprietaire, statut,
            lot_id, utilisateurs_json, notes_admin, importe_le, resolu_le
        FROM _lot_import_old
    """)
    op.execute("DROP TABLE _lot_import_old")
