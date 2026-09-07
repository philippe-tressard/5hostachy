"""Ajoute le champ non_applicable sur diagnostic_type."""

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column(
        "diagnostic_type",
        sa.Column("non_applicable", sa.Boolean(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("diagnostic_type", "non_applicable")
