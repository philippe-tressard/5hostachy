"""publication_syndic : affiche le commentaire en tête quand is_commentaire=True

Révision ID: 0109
Revises: 0108
Create Date: 2026-05-22

Bug : le template publication_syndic affichait toujours publication.contenu
(corps de la publication principale) même pour un commentaire. Le backend
passait correctement is_commentaire, commentaire et evolutions au contexte
mais le template ne les utilisait pas.

Cette migration met à jour le sujet ET le corps pour gérer les deux cas :
- is_commentaire=False → comportement identique à avant (titre + contenu)
- is_commentaire=True  → commentaire en tête, puis historique (publication
  initiale + commentaires précédents), puis CTA
"""
from alembic import op

revision = '0109'
down_revision = '0108'
branch_labels = None
depends_on = None


NEW_SUJET = (
    '{% if is_commentaire %}'
    '\U0001f4ac Commentaire sur « {{ publication.titre }} »'
    '{% else %}'
    '{% if reference_copro %}\U0001f3e2 {{ reference_copro }} — {% endif %}'
    'Nouvelle publication'
    '{% endif %}'
    ' — {{ residence.nom }}'
)

NEW_BODY = (
    # ── Titre conditionnel ──────────────────────────────────────────────────
    '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
    '{% if is_commentaire %}\U0001f4ac Nouveau commentaire'
    '{% else %}\U0001f4e2 Publication du conseil syndical{% endif %}'
    '</h2>'

    # ── Phrase d'introduction ───────────────────────────────────────────────
    '<p style="margin:0 0 16px">'
    '{% if is_commentaire %}'
    'Un nouveau commentaire a été ajouté sur la publication '
    '<strong>{{ publication.titre }}</strong> par '
    '{{ auteur.prenom }} {{ auteur.nom }}'
    '{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.'
    '{% else %}'
    'Une publication a été transmise à votre attention par le conseil '
    'syndical de <strong>{{ residence.nom }}</strong>'
    '{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.'
    '{% endif %}'
    '</p>'

    # ── Bloc commentaire (is_commentaire=True uniquement) ───────────────────
    '{% if is_commentaire %}'
    '<table role="presentation" style="width:100%;margin:0 0 20px;'
    'border:2px solid #1E3A5F;border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#EEF2F7;padding:16px">'
    '<p style="margin:0 0 6px;font-size:13px;color:#5A6070;font-weight:600">'
    '{{ auteur.prenom }} {{ auteur.nom }} — {{ date_commentaire }}</p>'
    '<div style="font-size:14px;color:#1A1A2E">{{ commentaire | safe }}</div>'
    '{% if fichiers %}'
    '<p style="margin:8px 0 0;font-size:13px;color:#5A6070">'
    '\U0001f4ce Pièces jointes disponibles ci-dessous.</p>'
    '{% endif %}'
    '</td></tr></table>'

    # ── Séparateur historique ───────────────────────────────────────────────
    '<h3 style="margin:0 0 12px;font-size:13px;font-weight:600;color:#8A8FA0;'
    'text-transform:uppercase;letter-spacing:.5px">Historique</h3>'
    '{% endif %}'

    # ── Publication initiale ────────────────────────────────────────────────
    '<table role="presentation" style="width:100%;'
    'margin:0 0 {% if is_commentaire %}8{% else %}20{% endif %}px;'
    'border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#F2EFE9;padding:16px">'
    '{% if is_commentaire %}'
    '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">'
    'Publication initiale — {{ date_publication }}</p>'
    '{% endif %}'
    '<p style="margin:0 0 {% if is_commentaire %}8{% else %}12{% endif %}px;'
    'font-weight:700;font-size:16px;color:#1E3A5F">{{ publication.titre }}</p>'
    '<div style="font-size:14px;color:#1A1A2E">{{ publication.contenu | safe }}</div>'
    '</td></tr></table>'

    # ── Commentaires précédents (si historique) ─────────────────────────────
    '{% if is_commentaire and evolutions %}'
    '{% for e in evolutions %}'
    '<table role="presentation" style="width:100%;margin:0 0 8px;'
    'border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#FFFFFF;padding:12px 16px">'
    '<p style="margin:0 0 4px;font-size:12px;color:#8A8FA0">'
    '{{ e.auteur_nom }} — {{ e.date }}</p>'
    '<div style="font-size:14px;color:#1A1A2E">{{ e.contenu | safe }}</div>'
    '</td></tr></table>'
    '{% endfor %}'
    '{% endif %}'

    # ── CTA ─────────────────────────────────────────────────────────────────
    '<p style="text-align:center;margin:{% if is_commentaire %}16{% else %}0{% endif %}px 0 0">'
    '<a href="{{ app.url }}/actualites#pub-{{ publication.id }}" '
    'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;'
    'font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
    'Voir la publication</a></p>'
)

OLD_SUJET = (
    '{% if reference_copro %}\U0001f3e2 {{ reference_copro }} — {% endif %}'
    'Nouvelle publication — {{ residence.nom }}'
)

OLD_BODY = (
    '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
    '\U0001f4e2 Publication du conseil syndical</h2>'
    '<p style="margin:0 0 16px">Une publication a été transmise à votre attention '
    'par le conseil syndical de <strong>{{ residence.nom }}</strong>'
    '{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.</p>'
    '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;'
    'border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#F2EFE9;padding:16px">'
    '<p style="margin:0 0 12px;font-weight:700;font-size:16px;color:#1E3A5F">{{ publication.titre }}</p>'
    '<div style="font-size:14px;color:#1A1A2E">{{ publication.contenu | safe }}</div>'
    '</td></tr></table>'
    '<p style="text-align:center;margin:0"><a href="{{ app.url }}/actualites#pub-{{ publication.id }}" '
    'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;'
    'padding:12px 32px;border-radius:6px;text-decoration:none">Voir la publication</a></p>'
)


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def upgrade():
    op.execute(
        f"UPDATE modele_email SET sujet = {_q(NEW_SUJET)}, corps_html = {_q(NEW_BODY)} "
        f"WHERE code = 'publication_syndic'"
    )


def downgrade():
    op.execute(
        f"UPDATE modele_email SET sujet = {_q(OLD_SUJET)}, corps_html = {_q(OLD_BODY)} "
        f"WHERE code = 'publication_syndic'"
    )
