"""Préférence d'affichage : « n'afficher que les contenus de mes bâtiments ».

Les actualités ciblées sur un autre bâtiment que le sien ne parvenaient pas au
résident (#339). Elles lui parviennent désormais — la vie d'une copropriété se
passe rarement dans un seul bâtiment, et un chantier, une coupure ou une réunion
concernent souvent sans être « chez soi ». Ce champ rend l'ancien fonctionnement
à qui le préfère.

**Décochée pour tout le monde, y compris les comptes existants.** C'est le
nouveau comportement qui devient la règle ; la restriction est un choix, et un
choix ne se pose pas à la place de quelqu'un.

⚠️ Ce champ est une préférence d'**affichage**, jamais un droit. Il ne protège
rien : l'utilisateur peut le retirer quand il veut, et il ne s'applique qu'à ce
qu'il voyait déjà. La confidentialité reste portée par `public_cible` et par les
profils d'accès aux documents, que ce lot ne touche pas — une agence, un bailleur
non résident ou un mandataire qui n'avaient pas de visibilité n'en gagnent
aucune. Ne jamais le présenter, dans l'interface ou ailleurs, comme une mesure de
confidentialité.

Revision ID: 0144
Revises: 0143
Create Date: 2026-08-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0144"
down_revision = "0143"
branch_labels = None
depends_on = None

TABLE = "utilisateur"
COLONNE = "restreindre_a_mes_batiments"


def _colonnes(table: str) -> set:
    """Colonnes réellement présentes, lues sur la base en cours de migration.

    Même précaution qu'en 0137 et 0142 : ajouter une colonne déjà présente ferait
    échouer `alembic upgrade`, et `start.sh` a `set -e` — le conteneur ne
    démarrerait plus, sur les deux nœuds.
    """
    inspecteur = sa.inspect(op.get_bind())
    return {c["name"] for c in inspecteur.get_columns(table)}


def upgrade() -> None:
    if COLONNE in _colonnes(TABLE):
        return
    #  `server_default="0"` et non `nullable=True` : la règle de visibilité lit ce
    #  drapeau à chaque publication affichée, et un NULL l'obligerait à traiter
    #  « inconnu » comme « décoché » — c'est-à-dire à écrire ailleurs la valeur par
    #  défaut, qui n'aurait alors plus de source unique.
    op.add_column(
        TABLE,
        sa.Column(COLONNE, sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    if COLONNE not in _colonnes(TABLE):
        return
    op.drop_column(TABLE, COLONNE)
