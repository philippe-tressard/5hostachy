"""0030 — Add fonction column to utilisateur + fix FAQ category name to 5Hostachy"""

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


def upgrade():
    with op.batch_alter_table('utilisateur') as batch_op:
        batch_op.add_column(sa.Column('fonction', sa.String(), nullable=True))

    # Mise à jour du nom de catégorie FAQ dans les données existantes
    op.execute(
        text("UPDATE faq_item SET categorie = :new WHERE categorie IN (:old1, :old2)").bindparams(
            new="\U0001f4f1 Application 5Hostachy",
            old1="\U0001f4f1 Application Hostachy",
            old2="Application Hostachy",
        )
    )


def downgrade():
    with op.batch_alter_table('utilisateur') as batch_op:
        batch_op.drop_column('fonction')
