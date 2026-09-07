"""Ajout config email_footer + fix sujet nouvel_arrivant_bal (reference_copro).

Revision ID: 0090
Revises: 0089
Create Date: 2026-04-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Ajouter email_footer dans config_site (similaire à whatsapp_footer)
    conn.execute(
        sa.text(
            "INSERT OR IGNORE INTO config_site (cle, valeur) "
            "VALUES ('email_footer', '— Envoyé depuis 5hostachy.fr')"
        )
    )

    # S'assurer que reference_copro existe (peut avoir été créé par mig 0084)
    conn.execute(
        sa.text(
            "INSERT OR IGNORE INTO config_site (cle, valeur) "
            "VALUES ('reference_copro', '')"
        )
    )

    # Corriger le sujet du template nouvel_arrivant_bal : remplacer "00213"
    # hardcodé par la variable {{ reference_copro }}
    conn.execute(
        sa.text(
            "UPDATE modele_email "
            "SET sujet = '{{ reference_copro }} - Nouvel arrivant MaJ Boites aux lettres' "
            "WHERE code = 'nouvel_arrivant_bal' "
            "AND sujet = '00213 - Nouvel arrivant MaJ Boites aux lettres'"
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM config_site WHERE cle = 'email_footer'")
    )
    conn.execute(
        sa.text(
            "UPDATE modele_email "
            "SET sujet = '00213 - Nouvel arrivant MaJ Boites aux lettres' "
            "WHERE code = 'nouvel_arrivant_bal' "
            "AND sujet = '{{ reference_copro }} - Nouvel arrivant MaJ Boites aux lettres'"
        )
    )
