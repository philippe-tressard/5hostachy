"""Deux modèles d'e-mail portaient un bouton vers une page qui n'existe pas.

Ni `/documents` ni `/admin/utilisateurs` n'ont jamais été des routes du front.
C'est le même 404 que celui signalé depuis un PV d'AG le 26/07/2026, qui avait
donné naissance à `app/utils/liens.py` et à `tests/test_liens_front.py` — sauf
que ce garde-fou ne lit que les `lien=` fabriqués en Python, jamais les URL
écrites en dur dans le HTML d'un modèle. Les deux lui ont donc échappé.

- `document_publie` → `/documents` : il n'existe pas de page « tous les
  documents », chaque document s'affiche là où il est rattaché. Le bouton pointe
  désormais vers `document.lien`, fourni au rendu depuis `EMPLACEMENTS`. Ce
  modèle n'était envoyé par personne, ce qui explique que rien ne l'ait signalé :
  un lien mort dans un e-mail que personne n'expédie ne se voit nulle part.

- `compte_en_attente` → `/admin/utilisateurs` : celui-ci **part réellement**, au
  gestionnaire du site, à chaque demande de compte. Son bouton « Valider le
  compte » ouvrait un 404 depuis l'origine. La page `/admin` s'ouvre justement
  sur l'onglet « Comptes en attente » — et elle ne lit pas `?onglet=`, donc le
  lien nu est le bon.

`REPLACE()` ciblé plutôt qu'un `UPDATE` du corps entier : toute personnalisation
faite depuis Admin → Emails survit, et la clause `WHERE` rend la migration
idempotente comme sans effet sur un modèle déjà réécrit à la main.

Revision ID: 0128
Revises: 0127
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0128"
down_revision = "0127"
branch_labels = None
depends_on = None

_STYLE_DOC = (
    'style="display:inline-block;background:#3D6B4F;color:#ffffff;'
    'font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;'
    'text-decoration:none"'
)
_STYLE_ADMIN = (
    'style="display:inline-block;background:#1E3A5F;color:#ffffff;'
    'font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;'
    'text-decoration:none"'
)

# (code, fragment d'origine, fragment corrigé)
_CORRECTIONS = [
    (
        "document_publie",
        f'<a href="{{{{ app.url }}}}/documents" {_STYLE_DOC}>Consulter les documents</a>',
        f'<a href="{{{{ app.url }}}}{{{{ document.lien }}}}" {_STYLE_DOC}>Consulter le document</a>',
    ),
    (
        "compte_en_attente",
        f'<a href="{{{{ app.url }}}}/admin/utilisateurs" {_STYLE_ADMIN}>Valider le compte</a>',
        f'<a href="{{{{ app.url }}}}/admin" {_STYLE_ADMIN}>Valider le compte</a>',
    ),
]


def _remplacer(conn, code: str, ancien: str, nouveau: str) -> None:
    conn.execute(
        sa.text(
            "UPDATE modele_email SET corps_html = REPLACE(corps_html, :ancien, :nouveau) "
            "WHERE code = :code AND instr(corps_html, :ancien) > 0"
        ).bindparams(code=code, ancien=ancien, nouveau=nouveau)
    )


def upgrade():
    conn = op.get_bind()
    for code, ancien, nouveau in _CORRECTIONS:
        _remplacer(conn, code, ancien, nouveau)


def downgrade():
    conn = op.get_bind()
    for code, ancien, nouveau in _CORRECTIONS:
        _remplacer(conn, code, nouveau, ancien)
