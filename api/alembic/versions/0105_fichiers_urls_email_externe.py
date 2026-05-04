"""Add fichiers_urls to message_ticket, ticket_evolution, publication_evolution + email templates"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = '0105'
down_revision = '0104'
branch_labels = None
depends_on = None


def _column_exists(bind, table, column):
    cols = [row[1] for row in bind.execute(text(f"PRAGMA table_info({table})"))]
    return column in cols


def upgrade():
    bind = op.get_bind()

    # ── Colonnes fichiers_urls (idempotent) ─────────────────────────────────
    for table in ('message_ticket', 'ticket_evolution', 'publication_evolution'):
        if not _column_exists(bind, table, 'fichiers_urls'):
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(sa.Column('fichiers_urls', sa.Text(), nullable=False, server_default='[]'))

    # ── Templates email ─────────────────────────────────────────────────────

    # Template publication_externe
    existing = bind.execute(
        text("SELECT id FROM modele_email WHERE code = 'publication_externe'")
    ).fetchone()
    if not existing:
        bind.execute(text("""
            INSERT INTO modele_email (code, libelle, sujet, corps, actif)
            VALUES (
                'publication_externe',
                'Notification publication (email externe)',
                :sujet,
                :corps,
                1
            )
        """).bindparams(
            sujet='{% if is_commentaire %}Relance {{ publication.titre }}{% else %}{{ publication.titre }} — {{ residence.nom }}{% endif %}',
            corps=(
                '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
                '{% if is_commentaire %}💬 Nouveau commentaire{% else %}📢 Publication{% endif %} : {{ publication.titre }}</h2>'

                # ── Nouveau commentaire en tête ──
                '{% if is_commentaire %}'
                '<table role="presentation" style="width:100%;margin:0 0 20px;border:2px solid #1E3A5F;border-radius:8px;overflow:hidden"><tr>'
                '<td style="background:#EEF2F7;padding:16px">'
                '<p style="margin:0 0 6px;font-size:13px;color:#5A6070;font-weight:600">{{ auteur.prenom }} {{ auteur.nom }} — {{ date_commentaire }}</p>'
                '<div style="font-size:14px;color:#1A1A2E">{{ commentaire | safe }}</div>'
                '{% if fichiers %}'
                '<p style="margin:8px 0 0;font-size:13px;color:#5A6070">📎 Voir les pièces jointes ci-dessous.</p>'
                '{% endif %}'
                '</td></tr></table>'

                # ── Historique ──
                '<h3 style="margin:0 0 12px;font-size:14px;font-weight:600;color:#5A6070;text-transform:uppercase;letter-spacing:.5px">Historique</h3>'
                '{% endif %}'

                # ── Publication initiale ──
                '<table role="presentation" style="width:100%;margin:0 0 {% if is_commentaire %}8{% else %}20{% endif %}px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
                '<td style="background:#F2EFE9;padding:16px">'
                '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Publication initiale — {{ date_publication }}</p>'
                '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ publication.titre }}</p>'
                '<div style="font-size:14px;color:#1A1A2E">{{ publication.contenu | safe }}</div>'
                '</td></tr></table>'

                # ── Évolutions précédentes ──
                '{% if is_commentaire and evolutions %}'
                '{% for e in evolutions %}'
                '<table role="presentation" style="width:100%;margin:0 0 8px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
                '<td style="background:#FFFFFF;padding:12px 16px">'
                '<p style="margin:0 0 4px;font-size:12px;color:#8A8FA0">{{ e.auteur_nom }} — {{ e.date }}</p>'
                '<div style="font-size:14px;color:#1A1A2E">{{ e.contenu | safe }}</div>'
                '</td></tr></table>'
                '{% endfor %}'
                '{% endif %}'

                # ── Bas de page externe ──
                '<hr style="border:none;border-top:1px solid #D0D8E4;margin:20px 0 16px">'
                '<p style="margin:0;font-size:13px;color:#5A6070;text-align:center">'
                'Ce message vous a été transmis par le Conseil Syndical de la copropriété <strong>{{ residence.nom }}</strong>.</p>'
            )
        ))

    # Template ticket_externe
    existing = bind.execute(
        text("SELECT id FROM modele_email WHERE code = 'ticket_externe'")
    ).fetchone()
    if not existing:
        bind.execute(text("""
            INSERT INTO modele_email (code, libelle, sujet, corps, actif)
            VALUES (
                'ticket_externe',
                'Notification ticket (email externe)',
                :sujet,
                :corps,
                1
            )
        """).bindparams(
            sujet='{% if is_commentaire %}Relance Ticket #{{ ticket.numero }} — {{ ticket.titre }}{% else %}Ticket #{{ ticket.numero }} — {{ ticket.titre }}{% endif %}',
            corps=(
                '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
                '{% if is_commentaire %}💬 Nouveau commentaire{% else %}🔧 Ticket{% endif %} : {{ ticket.titre }}</h2>'

                # ── Nouveau message/commentaire en tête ──
                '{% if is_commentaire %}'
                '<table role="presentation" style="width:100%;margin:0 0 20px;border:2px solid #1E3A5F;border-radius:8px;overflow:hidden"><tr>'
                '<td style="background:#EEF2F7;padding:16px">'
                '<p style="margin:0 0 6px;font-size:13px;color:#5A6070;font-weight:600">{{ auteur.prenom }} {{ auteur.nom }} — {{ date_commentaire }}</p>'
                '<div style="font-size:14px;color:#1A1A2E">{{ commentaire | safe }}</div>'
                '{% if fichiers %}'
                '<p style="margin:8px 0 0;font-size:13px;color:#5A6070">📎 Voir les pièces jointes ci-dessous.</p>'
                '{% endif %}'
                '</td></tr></table>'

                # ── Historique ──
                '<h3 style="margin:0 0 12px;font-size:14px;font-weight:600;color:#5A6070;text-transform:uppercase;letter-spacing:.5px">Historique</h3>'
                '{% endif %}'

                # ── Description initiale ──
                '<table role="presentation" style="width:100%;margin:0 0 {% if is_commentaire %}8{% else %}20{% endif %}px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
                '<td style="background:#F2EFE9;padding:16px">'
                '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #{{ ticket.numero }}{% if ticket.categorie %} · {{ ticket.categorie }}{% endif %} — {{ date_creation }}</p>'
                '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
                '<div style="font-size:14px;color:#1A1A2E">{{ ticket.description | safe }}</div>'
                '</td></tr></table>'

                # ── Messages précédents ──
                '{% if is_commentaire and messages %}'
                '{% for m in messages %}'
                '<table role="presentation" style="width:100%;margin:0 0 8px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
                '<td style="background:#FFFFFF;padding:12px 16px">'
                '<p style="margin:0 0 4px;font-size:12px;color:#8A8FA0">{{ m.auteur_nom }} — {{ m.date }}</p>'
                '<div style="font-size:14px;color:#1A1A2E">{{ m.contenu | safe }}</div>'
                '</td></tr></table>'
                '{% endfor %}'
                '{% endif %}'

                # ── Bas de page externe ──
                '<hr style="border:none;border-top:1px solid #D0D8E4;margin:20px 0 16px">'
                '<p style="margin:0;font-size:13px;color:#5A6070;text-align:center">'
                'Ce message vous a été transmis par le Conseil Syndical de la copropriété <strong>{{ residence.nom }}</strong>.</p>'
            )
        ))


def downgrade():
    with op.batch_alter_table('publication_evolution') as batch_op:
        batch_op.drop_column('fichiers_urls')

    with op.batch_alter_table('ticket_evolution') as batch_op:
        batch_op.drop_column('fichiers_urls')

    with op.batch_alter_table('message_ticket') as batch_op:
        batch_op.drop_column('fichiers_urls')

    op.get_bind().execute(text("DELETE FROM modele_email WHERE code IN ('publication_externe', 'ticket_externe')"))
