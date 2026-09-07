"""ticket_syndic: style moderne, lien ticket CTA, suppression footer redondant.

CONVENTION : toute migration qui met à jour un modele_email doit importer le
contenu depuis seed.EMAIL_TEMPLATES — ne jamais redéclarer le HTML inline.
Cela garantit une source de vérité unique et évite les divergences.
"""
from alembic import op
import sqlalchemy as sa

revision = '0108'
down_revision = '0107'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Import depuis seed.py (source de vérité unique pour les templates) ──
    from app.seed import EMAIL_TEMPLATES
    tpl = next(t for t in EMAIL_TEMPLATES if t[0] == 'ticket_syndic')
    _code, _libelle, sujet, corps_html, _desactivable = tpl

    corps_texte = (
        '{% if reference_copro %}[{{ reference_copro }}] {% endif %}'
        'Ticket #{{ ticket.numero }} — {{ ticket.titre }}\n'
        'Auteur\u202f: {{ auteur.prenom }} {{ auteur.nom }}\n'
        '{% if ticket.description %}Détail\u202f: {{ ticket.description }}\n{% endif %}'
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
