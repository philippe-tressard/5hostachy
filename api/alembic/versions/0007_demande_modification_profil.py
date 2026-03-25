"""Table demande_modification_profil

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "demande_modification_profil" not in tables:
        op.create_table(
            "demande_modification_profil",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("utilisateur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False, index=True),
            sa.Column("statut_souhaite", sa.String(), nullable=True),
            sa.Column("batiment_id_souhaite", sa.Integer(), sa.ForeignKey("batiment.id"), nullable=True),
            sa.Column("motif", sa.String(), nullable=True),
            sa.Column("statut_demande", sa.String(), nullable=False, server_default="en_attente"),
            sa.Column("motif_refus", sa.String(), nullable=True),
            sa.Column("traite_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
            sa.Column("cree_le", sa.DateTime(), nullable=False),
            sa.Column("traite_le", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("demande_modification_profil")
