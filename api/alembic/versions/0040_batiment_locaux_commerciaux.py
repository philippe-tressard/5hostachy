"""0040 — Batiment : nb_locaux_commerciaux + correction nb_appartements bât 4 (23→21)"""

revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column('batiment', sa.Column('nb_locaux_commerciaux', sa.Integer(), nullable=False, server_default='0'))

    conn = op.get_bind()
    # Bâtiment 4 : 2 locaux commerciaux ; nb_appartements corrigé 23→21
    conn.execute(sa.text("UPDATE batiment SET nb_locaux_commerciaux=2, nb_appartements=21 WHERE numero='4'"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE batiment SET nb_appartements=23 WHERE numero='4'"))
    op.drop_column('batiment', 'nb_locaux_commerciaux')
