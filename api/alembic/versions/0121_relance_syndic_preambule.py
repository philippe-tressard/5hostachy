"""Préambule partenarial + ancienneté réelle dans le modèle relance_syndic.

Le seed n'insère un modèle que s'il est ABSENT (`if not ... first()`), donc
modifier `seed.EMAIL_TEMPLATES` ne change rien à une base existante : sans cette
migration, la production continuerait d'envoyer l'ancien texte.

`REPLACE()` plutôt qu'un `UPDATE` du corps entier : chirurgical, et surtout toute
personnalisation faite par le CS depuis Admin → Emails sur le RESTE du modèle
(liste des tickets, formule de politesse) survit. La clause `WHERE` porte sur le
fragment d'origine, ce qui rend la migration idempotente et sans effet sur un
modèle déjà réécrit à la main.

Revision ID: 0121
Revises: 0120
Create Date: 2026-08-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0121"
down_revision = "0120"
branch_labels = None
depends_on = None

_ANCIEN_TITRE = "Relance ticket(s) non résolu(s) depuis 1 mois"
_NOUVEAU_TITRE = "Relance ticket(s) sans avancée depuis {{ anciennete }}"

_ANCIEN_P = (
    '<p style="margin:0 0 20px">Le Conseil Syndical de la copropriété '
    "<strong>{{ residence.nom }}</strong> vous adresse la présente relance "
    "concernant les ticket(s) ci-dessous, transmis au syndic et restés "
    "<strong>sans avancées depuis plus d’un mois</strong>.</p>"
)

_NOUVEAU_P = (
    '<p style="margin:0 0 16px">Le Conseil Syndical de la copropriété '
    "<strong>{{ residence.nom }}</strong> se permet de revenir vers vous "
    "concernant les tickets ci-dessous, transmis au syndic et toujours "
    "<strong>sans avancée après {{ anciennete }}</strong>.</p>"
    '<p style="margin:0 0 16px">Nous mesurons la charge qui pèse sur la gestion '
    "d’un portefeuille de copropriétés. C’est précisément pour vous éviter des "
    "sollicitations répétées que nous regroupons ici l’ensemble des dossiers en "
    "attente. Leur ancienneté commence toutefois à nourrir un mécontentement "
    "que nous préférerions désamorcer ensemble.</p>"
    '<p style="margin:0 0 20px">Un simple point d’étape, même succinct, sur '
    "chacun d’eux nous permettrait de rassurer les résidents.</p>"
)


def _remplacer(conn, colonne: str, ancien: str, nouveau: str) -> None:
    conn.execute(
        sa.text(
            f"UPDATE modele_email SET {colonne} = REPLACE({colonne}, :ancien, :nouveau) "
            "WHERE code = 'relance_syndic' AND instr(" + colonne + ", :ancien) > 0"
        ).bindparams(ancien=ancien, nouveau=nouveau)
    )


def upgrade():
    conn = op.get_bind()
    # Le « depuis 1 mois » figé du sujet et du titre devient l'ancienneté réelle.
    _remplacer(conn, "sujet", _ANCIEN_TITRE, _NOUVEAU_TITRE)
    _remplacer(conn, "corps_html", _ANCIEN_TITRE, _NOUVEAU_TITRE)
    _remplacer(conn, "corps_html", _ANCIEN_P, _NOUVEAU_P)


def downgrade():
    conn = op.get_bind()
    _remplacer(conn, "corps_html", _NOUVEAU_P, _ANCIEN_P)
    _remplacer(conn, "corps_html", _NOUVEAU_TITRE, _ANCIEN_TITRE)
    _remplacer(conn, "sujet", _NOUVEAU_TITRE, _ANCIEN_TITRE)
