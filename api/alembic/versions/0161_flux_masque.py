"""flux_masque — les cartes du fil retirées de la vue par un administrateur

Demandé le 31/08/2026 : *« supprimer, uniquement pour l'admin sur le fil
d'actualité — celle-ci reste tracée à l'origine : actualité, annuaire,
ticket… »*

🔴 Le fil est une vue CALCULÉE à partir de sept sources. Cette table ne porte
donc que des identifiants d'AFFICHAGE (`pub_7`, `mcs_12`, `tk_15`) : aucun objet
n'est supprimé, et il n'y a aucune clé étrangère à poser — deux sources peuvent
porter le même numéro, c'est le préfixe qui les distingue.

Revision ID: 0161
Revises: 0160
"""
import sqlalchemy as sa
from alembic import op

revision = "0161"
down_revision = "0160"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flux_masque",
        sa.Column("id", sa.Integer(), primary_key=True),
        #  UNIQUE : masquer deux fois la même carte est le même fait, pas deux.
        sa.Column("item_id", sa.String(), nullable=False, unique=True, index=True),
        #  NULLABLE, et délibérément : si le compte disparaît, c'est le LIEN qui
        #  part, pas le masquage. La leçon du 31/08/2026, où une purge a effacé
        #  un membre du conseil syndical pour réparer une référence cassée.
        sa.Column("masque_par_id", sa.Integer(), sa.ForeignKey("utilisateur.id"), nullable=True),
        sa.Column("masque_le", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("flux_masque")
