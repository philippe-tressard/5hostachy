"""0057 — DiagnosticRapport : ajout colonne synthese (texte optionnel)."""
from alembic import op
import sqlalchemy as sa


revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("diagnostic_rapport", sa.Column("synthese", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("diagnostic_rapport", "synthese")
