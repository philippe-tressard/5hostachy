"""Contrats d'entretien : durée initiale, fréquence, documents

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    # Modifier la table contrat_entretien
    with op.batch_alter_table("contrat_entretien") as batch_op:
        batch_op.drop_column("date_fin")
        batch_op.add_column(sa.Column("duree_initiale_valeur", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("duree_initiale_unite", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("frequence_type", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("frequence_valeur", sa.Integer(), nullable=True))

    # Créer la table document_contrat
    op.create_table(
        "document_contrat",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contrat_id", sa.Integer(), sa.ForeignKey("contrat_entretien.id"), nullable=False),
        sa.Column("fichier_nom", sa.String(), nullable=False),
        sa.Column("fichier_chemin", sa.String(), nullable=False),
        sa.Column("upload_le", sa.DateTime(), nullable=False),
        sa.Column("uploader_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
    )


def downgrade():
    op.drop_table("document_contrat")

    with op.batch_alter_table("contrat_entretien") as batch_op:
        batch_op.drop_column("frequence_valeur")
        batch_op.drop_column("frequence_type")
        batch_op.drop_column("duree_initiale_unite")
        batch_op.drop_column("duree_initiale_valeur")
        batch_op.add_column(sa.Column("date_fin", sa.Date(), nullable=True))
