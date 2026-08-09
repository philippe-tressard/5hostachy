"""Formule d'appel de `relance_syndic` : la gestionnaire ET l'assistante de gestion.

Le cabinet fonctionne en binôme — l'assistante supplée la gestionnaire en son
absence — et les deux partagent la même boîte. La formule d'appel n'en nommait
qu'une : « Madame Céline Mariette, ». Elle nomme désormais les deux, sans prénom :
« Madame Mariette, Madame Thauvin, ».

Les personnes ne sont **pas** écrites en dur : `interlocuteurs_syndic()` les lit
dans l'annuaire en sélectionnant les fonctions « gestionnaire » et « assistant »
(la comptable en est exclue : elle traite les appels de fonds, pas les
signalements). Le cabinet change de personnel, l'annuaire est la seule source qui
suive.

`REPLACE()` ciblé, sur le modèle de la 0131 : la personnalisation faite depuis
Admin → Emails sur le reste du modèle survit, et la clause `WHERE` rend la
migration idempotente. Le contexte continue de fournir `civilite` et
`nom_gestionnaire` : une base qui n'aurait pas encore migré rend donc toujours
une formule correcte, plutôt qu'une variable indéfinie — que Jinja remplace par
du vide sans rien signaler.

Revision ID: 0133
Revises: 0132
Create Date: 2026-08-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0133"
down_revision = "0132"
branch_labels = None
depends_on = None

_ANCIENNE = "{{ civilite }} {{ nom_gestionnaire }},"
_NOUVELLE = "{{ interlocuteurs }},"


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
