"""Ajout template email ticket_nouveau_message.

Revision ID: 0095
Revises: 0094
Create Date: 2026-04-16
"""
from alembic import op
from sqlalchemy import text

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    exists = conn.execute(text("SELECT 1 FROM modele_email WHERE code = 'ticket_nouveau_message'")).fetchone()
    if not exists:
        conn.execute(
            text(
                "INSERT INTO modele_email (code, libelle, sujet, corps_html, corps_texte, variables_disponibles, actif, desactivable)"
                " VALUES (:code, :libelle, :sujet, :corps_html, :corps_texte, :variables, 1, 1)"
            ).bindparams(
                code="ticket_nouveau_message",
                libelle="Nouveau message sur un ticket",
                sujet="Nouveau message — Ticket #{{ ticket.numero }} — {{ residence.nom }}",
                corps_html=(
                    '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
                    "\U0001f4ac Nouveau message sur votre ticket</h2>"
                    "<p style=\"margin:0 0 16px\">Un nouveau message a été ajouté sur le ticket "
                    "<strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> "
                    "par {{ auteur_action.prenom }} {{ auteur_action.nom }}\u202f:</p>"
                    '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
                    '<td style="background:#F2EFE9;padding:16px">'
                    '<p style="margin:0;font-size:14px;color:#1A1A2E">{{ message.contenu }}</p>'
                    "</td></tr></table>"
                    '<p style="text-align:center;margin:0">'
                    '<a href="{{ app.url }}/tickets/{{ ticket.id }}" '
                    'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
                    "Voir le ticket</a></p>"
                ),
                corps_texte="",
                variables='["ticket", "message", "auteur_action", "residence", "app"]',
            )
        )


def downgrade():
    op.get_bind().execute(text("DELETE FROM modele_email WHERE code = 'ticket_nouveau_message'"))
