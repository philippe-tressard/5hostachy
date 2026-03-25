"""Ajoute statut/brouillon/statut_change_le sur publication + table publication_evolution."""

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column("publication", sa.Column("statut", sa.String(), nullable=True))
    op.add_column("publication", sa.Column("brouillon", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("publication", sa.Column("statut_change_le", sa.DateTime(), nullable=True))

    op.create_table(
        "publication_evolution",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("publication_id", sa.Integer(), sa.ForeignKey("publication.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(), nullable=False),          # commentaire | etat | correction
        sa.Column("contenu", sa.Text(), nullable=True),
        sa.Column("ancien_statut", sa.String(), nullable=True),
        sa.Column("nouveau_statut", sa.String(), nullable=True),
        sa.Column("auteur_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=False),
        sa.Column("cree_le", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("publication_evolution")
    op.drop_column("publication", "statut_change_le")
    op.drop_column("publication", "brouillon")
    op.drop_column("publication", "statut")
