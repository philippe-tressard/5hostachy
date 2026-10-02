"""Changer d'adresse : la nouvelle attend sa confirmation sur le jeton (#1549, 02/10/2026)

Changer l'adresse d'un compte la remplaçait sur-le-champ, sans mot de passe ni
re-vérification. Désormais la nouvelle adresse est confirmée par un lien à usage
unique avant de remplacer l'ancienne, qui reste celle du compte jusque-là.

Elle attend sur le jeton qui la confirmera : `email_verification_token`, la
table du lien de vérification de l'inscription — le même mécanisme, pas une
copie. Une ligne sans `nouvelle_adresse` vérifie l'adresse du compte ; une ligne
qui en porte une confirme ce changement.

Colonne simple, nullable : les jetons existants vérifient une inscription et
n'en ont pas. Aucune clé étrangère (SQLite n'en ajoute pas à une table
existante — CLAUDE.md, « Migrations Alembic »).

⚠️ Le nom de table et de colonne sont des CONSTANTES du fichier.

Revision ID: 0248
Revises: 0247
"""

import sqlalchemy as sa
from alembic import op

revision = "0248"
down_revision = "0247"
branch_labels = None
depends_on = None

TABLE = "email_verification_token"
COLONNE = "nouvelle_adresse"


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if COLONNE not in _colonnes(TABLE):
        op.add_column(TABLE, sa.Column(COLONNE, sa.String(), nullable=True))


def downgrade() -> None:
    if COLONNE in _colonnes(TABLE):
        op.drop_column(TABLE, COLONNE)
