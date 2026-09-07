"""Ajoute nom_proprietaire sur la table utilisateur (pour les locataires)."""

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        "utilisateur",
        sa.Column("nom_proprietaire", sa.String(), nullable=True),
    )


def downgrade():
    op.drop_column("utilisateur", "nom_proprietaire")
