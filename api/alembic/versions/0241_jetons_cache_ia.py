"""Coût de l'assistant : le CACHE compté, et les prix en DOLLARS (30/09/2026)

## Le cache, troisième prix

OpenAI met en cache, sans qu'on le demande, le début d'un prompt déjà vu (plus
de 1 024 jetons — nos consignes les dépassent) et facture cette part environ
dix fois moins cher. Un troisième prix se saisit donc par usage
(`llm_<usage>_prix_cache`), et le journal dit quelle part de l'entrée était en
cache (`appel_ia.jetons_cache`), pour que le coût estimé l'applique.

Colonne simple, nullable : les appels déjà journalisés n'en savent rien, et
leur coût reste calculé comme avant — tout au prix d'entrée.

## Les prix en dollars, comme les grilles

Arbitré le même jour : les prix se saisissent en DOLLARS par million de jetons,
en texte décimal (« 0.075 »), et plus en centimes d'euro entiers. Les valeurs
déjà saisies sont des centimes : elles sont divisées par cent, sans conversion
de devise — le seul tarif saisi à ce jour (0.2 / 1.2) était celui de la grille
en dollars, tapé dans des champs qui disaient euros.

Une valeur qui n'est pas un entier de centimes est laissée telle quelle : elle
est déjà décimale, donc déjà dans la nouvelle forme.

⚠️ Le nom de table et de colonne sont des CONSTANTES du fichier ; les valeurs
se lient.

Revision ID: 0241
Revises: 0240
"""

from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision = "0241"
down_revision = "0240"
branch_labels = None
depends_on = None

TABLE = "appel_ia"
COLONNE = "jetons_cache"
#: Les deux prix qui existaient avant cette migration (0230).
SUFFIXES_PRIX = ("_prix_entree", "_prix_sortie")


def _colonnes(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _convertir(conn, diviser: bool) -> None:
    lignes = [
        (cle, valeur)
        for cle, valeur in conn.execute(sa.text("SELECT cle, valeur FROM config_site")).fetchall()
        if cle.startswith("llm_") and cle.endswith(SUFFIXES_PRIX)
    ]
    for cle, valeur in lignes:
        texte = (valeur or "").strip()
        if diviser:
            if not texte.isdigit():
                continue
            neuf = format((Decimal(texte) / 100).normalize(), "f")
        else:
            try:
                neuf = str(int((Decimal(texte) * 100).to_integral_value()))
            except ArithmeticError:
                continue
        conn.execute(
            sa.text("UPDATE config_site SET valeur = :v WHERE cle = :c").bindparams(v=neuf, c=cle)
        )


def upgrade() -> None:
    if COLONNE not in _colonnes(TABLE):
        op.add_column(TABLE, sa.Column(COLONNE, sa.Integer(), nullable=True))
    _convertir(op.get_bind(), diviser=True)


def downgrade() -> None:
    _convertir(op.get_bind(), diviser=False)
    if COLONNE in _colonnes(TABLE):
        op.drop_column(TABLE, COLONNE)
