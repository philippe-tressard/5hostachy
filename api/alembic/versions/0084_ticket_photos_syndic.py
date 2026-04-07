"""Ticket : photos, option destinataire syndic, config reference_copro, template email

Revision ID: 0084
Revises: 0083
Create Date: 2026-04-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Champs ticket (idempotent pour SQLite — la colonne peut déjà exister si migration partielle)
    conn = op.get_bind()
    columns = [row[1] for row in conn.execute(sa.text("PRAGMA table_info('ticket')"))]
    if "photos_urls" not in columns:
        op.add_column("ticket", sa.Column("photos_urls", sa.Text, nullable=True))
    if "destinataire_syndic" not in columns:
        op.add_column("ticket", sa.Column("destinataire_syndic", sa.Boolean, server_default="0", nullable=False))

    # Config : référence copropriété
    op.execute(
        "INSERT OR IGNORE INTO config_site (cle, valeur) VALUES ('reference_copro', '00213')"
    )

    # Template email ticket_syndic
    op.execute("""
        INSERT OR IGNORE INTO modele_email (code, libelle, sujet, corps_html, corps_texte, variables_disponibles, desactivable, actif)
        VALUES (
            'ticket_syndic',
            'Notification ticket au syndic',
            '{{ reference_copro }} : {{ ticket.titre }}',
            '<h2>Nouveau ticket copropriété</h2>'
            '<p><strong>Référence :</strong> {{ ticket.numero }}</p>'
            '<p><strong>Catégorie :</strong> {{ ticket.categorie }}</p>'
            '<p><strong>Titre :</strong> {{ ticket.titre }}</p>'
            '<p><strong>Description :</strong></p>'
            '<div>{{ ticket.description }}</div>'
            '<p><strong>Auteur :</strong> {{ auteur.prenom }} {{ auteur.nom }}</p>'
            '<p><strong>Résidence :</strong> {{ residence.nom }}</p>'
            '<hr>'
            '<p><em>Ce message a été envoyé depuis l''application <a href="{{ app.url }}">{{ residence.nom }}</a>.</em></p>',
            'Nouveau ticket {{ reference_copro }} : {{ ticket.titre }} — {{ ticket.description }}',
            '["ticket", "auteur", "residence", "app", "reference_copro"]',
            0,
            1
        )
    """)


def downgrade() -> None:
    op.drop_column("ticket", "photos_urls")
    op.drop_column("ticket", "destinataire_syndic")
    op.execute("DELETE FROM config_site WHERE cle = 'reference_copro'")
    op.execute("DELETE FROM modele_email WHERE code = 'ticket_syndic'")
