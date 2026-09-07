"""ticket_syndic : affiche le commentaire en tête quand is_commentaire=True

Révision ID: 0110
Revises: 0109
Create Date: 2026-05-22

Bug : lors de l'ajout d'un commentaire sur un ticket avec envoi syndic/CS,
le template ticket_syndic affichait body.contenu à la place de ticket.description
(la description originale du ticket). De plus, is_commentaire, commentaire et
messages (évolutions précédentes) n'étaient pas utilisés.

Cette migration met à jour le sujet ET le corps pour gérer les deux cas :
- is_commentaire=False → comportement inchangé (description + historique tableau)
- is_commentaire=True  → commentaire en tête (encadré bleu), puis description
  initiale + messages précédents, puis CTA
"""
from alembic import op

revision = '0110'
down_revision = '0109'
branch_labels = None
depends_on = None


NEW_SUJET = (
    '{% if is_commentaire %}'
    '\U0001f4ac Commentaire — Ticket #{{ ticket.numero }} — {{ residence.nom }}'
    '{% else %}'
    '{% if reference_copro %}\U0001f3e2 {{ reference_copro }} — {% endif %}'
    'Ticket #{{ ticket.numero }} — {{ residence.nom }}'
    '{% endif %}'
)

NEW_BODY = (
    # ── Titre conditionnel ──────────────────────────────────────────────────
    '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
    '{% if is_commentaire %}\U0001f4ac Nouveau commentaire'
    '{% else %}\U0001f4cb Ticket transmis par le conseil syndical{% endif %}'
    '</h2>'

    # ── Introduction ────────────────────────────────────────────────────────
    '<p style="margin:0 0 16px">'
    '{% if is_commentaire %}'
    'Un nouveau commentaire a été ajouté sur le ticket '
    '<strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> '
    'par {{ auteur.prenom }} {{ auteur.nom }}'
    '{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.'
    '{% else %}'
    'Un ticket a été transmis à votre attention par le conseil syndical de '
    '<strong>{{ residence.nom }}</strong>'
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

    # ── Description initiale du ticket ──────────────────────────────────────
    '<table role="presentation" style="width:100%;'
    'margin:0 0 {% if is_commentaire %}8{% else %}20{% endif %}px;'
    'border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#F2EFE9;padding:16px">'
    '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">'
    'Ticket #{{ ticket.numero }}{% if ticket.categorie %} · {{ ticket.categorie }}{% endif %}'
    '{% if is_commentaire %} — Soumis le {{ date_creation }}{% endif %}'
    '</p>'
    '<p style="margin:0 0 {% if is_commentaire %}8{% else %}8{% endif %}px;'
    'font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
    '{% if ticket.description %}'
    '<div style="font-size:14px;color:#1A1A2E">{{ ticket.description | safe }}</div>'
    '{% endif %}'
    '{% if not is_commentaire %}'
    '<p style="margin:8px 0 0;font-size:14px;color:#5A6070">'
    'Soumis par {{ auteur.prenom }} {{ auteur.nom }}</p>'
    '{% endif %}'
    '</td></tr></table>'

    # ── Messages précédents (si historique de commentaires) ─────────────────
    '{% if is_commentaire and messages %}'
    '{% for m in messages %}'
    '<table role="presentation" style="width:100%;margin:0 0 8px;'
    'border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#FFFFFF;padding:12px 16px">'
    '<p style="margin:0 0 4px;font-size:12px;color:#8A8FA0">'
    '{{ m.auteur_nom }} — {{ m.date }}</p>'
    '<div style="font-size:14px;color:#1A1A2E">{{ m.contenu | safe }}</div>'
    '</td></tr></table>'
    '{% endfor %}'
    '{% endif %}'

    # ── Tableau historique résumé (création uniquement, si >1 entrées) ──────
    '{% if not is_commentaire and historique and historique|length > 1 %}'
    '<h3 style="margin:0 0 8px;font-size:15px;color:#1E3A5F">Historique</h3>'
    '<table role="presentation" style="border-collapse:collapse;width:100%;font-size:.88rem;'
    'margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden">'
    '{% for h in historique %}'
    '<tr style="background:{% if loop.index is odd %}#F2EFE9{% else %}#FFFFFF{% endif %}">'
    '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;'
    'white-space:nowrap;color:#5A6070;font-size:.82rem">{{ h.date }}</td>'
    '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;'
    'color:#1A1A2E">{{ h.label }}</td>'
    '</tr>{% endfor %}'
    '</table>'
    '{% endif %}'

    # ── CTA ─────────────────────────────────────────────────────────────────
    '<p style="text-align:center;margin:{% if is_commentaire %}16{% else %}0{% endif %}px 0 0">'
    '<a href="{{ app.url }}/tickets/{{ ticket.id }}" '
    'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;'
    'font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
    'Consulter le ticket</a></p>'
)

OLD_SUJET = (
    '{% if reference_copro %}\U0001f3e2 {{ reference_copro }} — {% endif %}'
    'Ticket #{{ ticket.numero }} — {{ residence.nom }}'
)

OLD_BODY = (
    '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
    '\U0001f4cb Ticket transmis par le conseil syndical</h2>'
    '<p style="margin:0 0 16px">Un ticket a été transmis à votre attention '
    'par le conseil syndical de <strong>{{ residence.nom }}</strong>'
    '{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.</p>'
    '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;'
    'border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#F2EFE9;padding:16px">'
    '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">'
    'Ticket #{{ ticket.numero }}{% if ticket.categorie %} · {{ ticket.categorie }}{% endif %}</p>'
    '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
    '{% if ticket.description %}'
    '<p style="margin:0 0 8px;font-size:14px;color:#1A1A2E">{{ ticket.description }}</p>'
    '{% endif %}'
    '<p style="margin:0;font-size:14px;color:#5A6070">Soumis par {{ auteur.prenom }} {{ auteur.nom }}</p>'
    '</td></tr></table>'
    '{% if historique and historique|length > 1 %}'
    '<h3 style="margin:0 0 8px;font-size:15px;color:#1E3A5F">Historique</h3>'
    '<table role="presentation" style="border-collapse:collapse;width:100%;font-size:.88rem;'
    'margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden">'
    '{% for h in historique %}'
    '<tr style="background:{% if loop.index is odd %}#F2EFE9{% else %}#FFFFFF{% endif %}">'
    '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;'
    'white-space:nowrap;color:#5A6070;font-size:.82rem">{{ h.date }}</td>'
    '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;'
    'color:#1A1A2E">{{ h.label }}</td>'
    '</tr>{% endfor %}'
    '</table>{% endif %}'
    '<p style="text-align:center;margin:0">'
    '<a href="{{ app.url }}/tickets/{{ ticket.id }}" '
    'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;'
    'font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
    'Consulter le ticket</a></p>'
)


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def upgrade():
    op.execute(
        f"UPDATE modele_email SET sujet = {_q(NEW_SUJET)}, corps_html = {_q(NEW_BODY)} "
        f"WHERE code = 'ticket_syndic'"
    )


def downgrade():
    op.execute(
        f"UPDATE modele_email SET sujet = {_q(OLD_SUJET)}, corps_html = {_q(OLD_BODY)} "
        f"WHERE code = 'ticket_syndic'"
    )
