"""Tables location_bail et remise_objet

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "location_bail" not in tables:
        op.create_table(
            "location_bail",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("lot_id", sa.Integer(), sa.ForeignKey("lot.id"), nullable=False),
            sa.Column("bailleur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
            sa.Column("locataire_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("locataire_nom", sa.String(), nullable=True),
            sa.Column("locataire_prenom", sa.String(), nullable=True),
            sa.Column("locataire_email", sa.String(), nullable=True),
            sa.Column("locataire_telephone", sa.String(), nullable=True),
            sa.Column("date_entree", sa.Date(), nullable=False),
            sa.Column("date_sortie_prevue", sa.Date(), nullable=True),
            sa.Column("date_sortie_reelle", sa.Date(), nullable=True),
            sa.Column("statut", sa.String(), nullable=False, server_default="actif"),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
            sa.Column("mis_a_jour_le", sa.DateTime(), nullable=False),
        )

    if "remise_objet" not in tables:
        op.create_table(
            "remise_objet",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("bail_id", sa.Integer(), sa.ForeignKey("location_bail.id"), nullable=False),
            sa.Column("type", sa.String(), nullable=False, server_default="autre"),
            sa.Column("libelle", sa.String(), nullable=False),
            sa.Column("quantite", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("reference", sa.String(), nullable=True),
            sa.Column("statut", sa.String(), nullable=False, server_default="en_possession"),
            sa.Column("remis_le", sa.Date(), nullable=True),
            sa.Column("rendu_le", sa.Date(), nullable=True),
            sa.Column("notes", sa.String(), nullable=True),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("remise_objet")
    op.drop_table("location_bail")
