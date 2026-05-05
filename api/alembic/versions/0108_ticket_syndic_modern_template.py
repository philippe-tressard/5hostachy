"""ticket_syndic: style moderne, lien ticket CTA, suppression footer redondant"""
from alembic import op
import sqlalchemy as sa

revision = '0108'
down_revision = '0107'
branch_labels = None
depends_on = None


def upgrade() -> None:
    sujet = (
        '{% if reference_copro %}\U0001f3e2 {{ reference_copro }} \u2014 {% endif %}'
        'Ticket #{{ ticket.numero }} \u2014 {{ residence.nom }}'
    )

    corps_html = (
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
        '\U0001f4cb Ticket transmis par le conseil syndical</h2>'
        '<p style="margin:0 0 16px">Un ticket a \u00e9t\u00e9 transmis \u00e0 votre attention par le conseil '
        'syndical de <strong>{{ residence.nom }}</strong>'
        '{% if reference_copro %} \u2014 r\u00e9f.\u202f{{ reference_copro }}{% endif %}.</p>'

        '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;'
        'border-radius:8px;overflow:hidden"><tr>'
        '<td style="background:#F2EFE9;padding:16px">'
        '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">'
        'Ticket #{{ ticket.numero }}{% if ticket.categorie %} \u00b7 {{ ticket.categorie }}{% endif %}</p>'
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
        '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;white-space:nowrap;'
        'color:#5A6070;font-size:.82rem">{{ h.date }}</td>'
        '<td style="padding:.35rem .75rem;border-bottom:1px solid #D0D8E4;color:#1A1A2E">{{ h.label }}</td>'
        '</tr>'
        '{% endfor %}'
        '</table>'
        '{% endif %}'

        '<p style="text-align:center;margin:0">'
        '<a href="{{ app.url }}/tickets/{{ ticket.id }}" '
        'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;'
        'font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
        'Consulter le ticket</a></p>'
    )

    corps_texte = (
        '{% if reference_copro %}[{{ reference_copro }}] {% endif %}'
        'Ticket #{{ ticket.numero }} \u2014 {{ ticket.titre }}\n'
        'Auteur\u202f: {{ auteur.prenom }} {{ auteur.nom }}\n'
        '{% if ticket.description %}D\u00e9tail\u202f: {{ ticket.description }}\n{% endif %}'
        '{% if historique and historique|length > 1 %}\n'
        'Historique\u202f:\n'
        '{% for h in historique %}- {{ h.date }}\u202f: {{ h.label }}\n{% endfor %}'
        '{% endif %}'
        '\nLien\u202f: {{ app.url }}/tickets/{{ ticket.id }}'
    )

    variables = '["ticket", "auteur", "residence", "app", "reference_copro", "historique"]'

    op.execute(
        sa.text(
            "UPDATE modele_email SET sujet = :sujet, corps_html = :corps_html,"
            " corps_texte = :corps_texte, variables_disponibles = :variables"
            " WHERE code = 'ticket_syndic'"
        ).bindparams(
            sujet=sujet,
            corps_html=corps_html,
            corps_texte=corps_texte,
            variables=variables,
        )
    )


def downgrade() -> None:
    pass
