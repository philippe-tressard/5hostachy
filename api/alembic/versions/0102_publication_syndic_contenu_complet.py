"""publication_syndic : contenu complet au lieu de l'extrait

Revision ID: 0102
Revises: 0101
Create Date: 2026-05-01
"""
from alembic import op

revision = '0102'
down_revision = '0101'
branch_labels = None
depends_on = None

NEW_BODY = (
    '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4e2 Publication du conseil syndical</h2>'
    '<p style="margin:0 0 16px">Une publication a été transmise à votre attention par le conseil syndical de <strong>{{ residence.nom }}</strong>{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.</p>'
    '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#F2EFE9;padding:16px">'
    '<p style="margin:0 0 12px;font-weight:700;font-size:16px;color:#1E3A5F">{{ publication.titre }}</p>'
    '<div style="font-size:14px;color:#1A1A2E">{{ publication.contenu | safe }}</div>'
    '</td></tr></table>'
    '<p style="text-align:center;margin:0"><a href="{{ app.url }}/actualites" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir la publication</a></p>'
)

OLD_BODY = (
    '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4e2 Publication du conseil syndical</h2>'
    '<p style="margin:0 0 16px">Une publication a été transmise à votre attention par le conseil syndical de <strong>{{ residence.nom }}</strong>{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.</p>'
    '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#F2EFE9;padding:16px">'
    '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ publication.titre }}</p>'
    '<p style="margin:0;font-size:14px;color:#1A1A2E">{{ publication.extrait }}</p>'
    '</td></tr></table>'
    '<p style="text-align:center;margin:0"><a href="{{ app.url }}/actualites" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir la publication</a></p>'
)


def upgrade():
    op.execute(
        f"UPDATE modele_email SET corps_html = {_q(NEW_BODY)} WHERE code = 'publication_syndic'"
    )


def downgrade():
    op.execute(
        f"UPDATE modele_email SET corps_html = {_q(OLD_BODY)} WHERE code = 'publication_syndic'"
    )


def _q(s: str) -> str:
    """Échappe une chaîne pour SQLite (guillemets simples)."""
    return "'" + s.replace("'", "''") + "'"
