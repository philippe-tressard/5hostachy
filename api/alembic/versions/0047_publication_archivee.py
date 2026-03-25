"""Ajoute le champ archivee sur la table publication."""

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("publication", sa.Column("archivee", sa.Boolean(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("publication", "archivee")
