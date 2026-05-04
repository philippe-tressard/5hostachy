"""Fix ticket_syndic template: description with | safe, exclude current evol from historique"""
from alembic import op
import sqlalchemy as sa

revision = '0107'
down_revision = '0106'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Correction : {{ ticket.description | safe }} pour rendre le HTML enrichi (RichEditor)
    # Note : la logique d'exclusion de l'évolution courante est dans le code Python (tickets.py)
    corps_html = (
        '<h2>Ticket copropriété #{{ ticket.numero }}</h2>'
        '<p><strong>Catégorie :</strong> {{ ticket.categorie }}</p>'
        '<p><strong>Titre :</strong> {{ ticket.titre }}</p>'
        '{% if ticket.description %}'
        '<p><strong>Commentaire :</strong></p>'
        '<div style="background:#f5f5f5;border-left:3px solid #999;padding:.6rem 1rem;margin:.5rem 0">{{ ticket.description | safe }}</div>'
        '{% endif %}'
        '<p><strong>Auteur :</strong> {{ auteur.prenom }} {{ auteur.nom }}</p>'
        '<p><strong>Résidence :</strong> {{ residence.nom }}</p>'
        '{% if historique and historique|length > 1 %}'
        '<h3 style="margin-top:1.2rem">Historique</h3>'
        '<table style="border-collapse:collapse;width:100%;font-size:.88rem">'
        '{% for h in historique %}'
        '<tr><td style="padding:.3rem .6rem;border:1px solid #ddd;white-space:nowrap;color:#666">{{ h.date }}</td>'
        '<td style="padding:.3rem .6rem;border:1px solid #ddd">{{ h.label }}</td></tr>'
        '{% endfor %}'
        '</table>'
        '{% endif %}'
        '<hr style="margin:1.5rem 0">'
        '<p style="font-size:.85rem;color:#888">'
        'Ce message a été envoyé depuis l\'application '
        '<a href="{{ app.url }}">{{ residence.nom }}</a>.'
        '</p>'
    )

    op.execute(
        sa.text(
            "UPDATE modele_email SET corps_html = :corps_html WHERE code = 'ticket_syndic'"
        ).bindparams(corps_html=corps_html)
    )


def downgrade() -> None:
    pass
