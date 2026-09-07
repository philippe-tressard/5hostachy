"""Crée la table releve_compteur."""

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table(
        "releve_compteur",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type_compteur", sa.String(), nullable=False),
        sa.Column("date_releve", sa.Date(), nullable=False),
        sa.Column("index", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("photo_url", sa.String(), nullable=True),
        sa.Column("prestataire_id", sa.Integer(), sa.ForeignKey("prestataire.id"), nullable=True),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
        sa.Column("cree_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
    )


def downgrade():
    op.drop_table("releve_compteur")
