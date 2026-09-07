"""Remplacement fichier_url par fichiers_urls (tableau JSON) sur devis_prestataire

Revision ID: 0056
Revises: 0055
"""
from alembic import op
import sqlalchemy as sa

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devis_prestataire") as batch_op:
        batch_op.add_column(sa.Column("fichiers_urls", sa.Text, nullable=True))

    # Migrer les URLs existantes vers un tableau JSON à un élément
    op.execute(
        "UPDATE devis_prestataire "
        "SET fichiers_urls = json_array(fichier_url) "
        "WHERE fichier_url IS NOT NULL"
    )

    with op.batch_alter_table("devis_prestataire") as batch_op:
        batch_op.drop_column("fichier_url")


def downgrade() -> None:
    with op.batch_alter_table("devis_prestataire") as batch_op:
        batch_op.add_column(sa.Column("fichier_url", sa.String, nullable=True))

    with op.batch_alter_table("devis_prestataire") as batch_op:
        batch_op.drop_column("fichiers_urls")
