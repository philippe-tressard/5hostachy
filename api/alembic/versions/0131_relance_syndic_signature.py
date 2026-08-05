"""Signature de `relance_syndic` : retirer le nom de la résidence.

« Le Conseil Syndical de {{ residence.nom }} » rendait « Le Conseil Syndical de
Les Hostachy » : l'article d'un nom propre ne se contracte pas, et la formule
sonnait faux dans un message adressé au syndic. Le destinataire sait de quelle
copropriété il s'agit — l'objet le porte, le préambule le répète.

`REPLACE()` ciblé : la personnalisation faite depuis Admin → Emails sur le reste
du modèle survit, et la clause `WHERE` rend la migration idempotente.

Revision ID: 0131
Revises: 0130
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0131"
down_revision = "0130"
branch_labels = None
depends_on = None

_ANCIENNE = "<strong>Le Conseil Syndical de {{ residence.nom }}</strong>"
_NOUVELLE = "<strong>Le Conseil Syndical</strong>"


def _remplacer(conn, ancien: str, nouveau: str) -> None:
    conn.execute(
        sa.text(
            "UPDATE modele_email SET corps_html = REPLACE(corps_html, :ancien, :nouveau) "
            "WHERE code = 'relance_syndic' AND instr(corps_html, :ancien) > 0"
        ).bindparams(ancien=ancien, nouveau=nouveau)
    )


def upgrade():
    _remplacer(op.get_bind(), _ANCIENNE, _NOUVELLE)


def downgrade():
    _remplacer(op.get_bind(), _NOUVELLE, _ANCIENNE)
