"""0038 — Batiment : champs composition (nb_appartements, nb_caves, nb_parkings) + Copropriete : nb_parkings_communs"""

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op


def upgrade() -> None:
    op.add_column('batiment', sa.Column('nb_appartements', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('batiment', sa.Column('nb_caves', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('batiment', sa.Column('nb_parkings', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('copropriete', sa.Column('nb_parkings_communs', sa.Integer(), nullable=False, server_default='0'))

    # Pré-remplissage depuis les données réelles (Excel "213 - liste des lots")
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE batiment SET nb_appartements=15, nb_caves=15 WHERE numero='1'"))
    conn.execute(sa.text("UPDATE batiment SET nb_appartements=15, nb_caves=15 WHERE numero='2'"))
    conn.execute(sa.text("UPDATE batiment SET nb_appartements=11, nb_caves=11 WHERE numero='3'"))
    conn.execute(sa.text("UPDATE batiment SET nb_appartements=23, nb_caves=20 WHERE numero='4'"))
    conn.execute(sa.text("UPDATE copropriete SET nb_parkings_communs=70"))


def downgrade() -> None:
    op.drop_column('copropriete', 'nb_parkings_communs')
    op.drop_column('batiment', 'nb_parkings')
    op.drop_column('batiment', 'nb_caves')
    op.drop_column('batiment', 'nb_appartements')
