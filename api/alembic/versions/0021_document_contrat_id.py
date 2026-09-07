"""Unifier DocumentContrat : ajout contrat_id sur document, suppression document_contrat

Revision ID: 0021
Revises: 0020
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    # Rendre categorie_id nullable et ajouter contrat_id sur document
    with op.batch_alter_table("document") as batch_op:
        batch_op.alter_column("categorie_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("contrat_id", sa.Integer(), nullable=True))

    # Supprimer l'ancienne table document_contrat
    op.drop_table("document_contrat")


def downgrade():
    op.create_table(
        "document_contrat",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contrat_id", sa.Integer(), sa.ForeignKey("contrat_entretien.id"), nullable=False),
        sa.Column("fichier_nom", sa.String(), nullable=False),
        sa.Column("fichier_chemin", sa.String(), nullable=False),
        sa.Column("upload_le", sa.DateTime(), nullable=False),
        sa.Column("uploader_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
    )
    with op.batch_alter_table("document") as batch_op:
        batch_op.drop_column("contrat_id")
        batch_op.alter_column("categorie_id", existing_type=sa.Integer(), nullable=False)
