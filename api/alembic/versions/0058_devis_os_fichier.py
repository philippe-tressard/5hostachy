"""0058 — DevisPrestataire : ajout colonne os_fichier_url (URL de l'OS signé)."""
from alembic import op
import sqlalchemy as sa


revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devis_prestataire", sa.Column("os_fichier_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("devis_prestataire", "os_fichier_url")
