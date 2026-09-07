"""Ajout modèle email 'nouvel_arrivant_bal' pour étiquette BAL syndic.

Revision ID: 0066
Revises: 0065
Create Date: 2026-03-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade():
    corps_html = (
        "<p>Bonjour,</p>"
        "<p>Nous vous informons de l'arrivée d'un nouveau résident :</p>"
        "<ul>"
        "<li><strong>Nom :</strong> {{ nom_complet }}</li>"
        "{% if batiment %}<li><strong>Bâtiment / Apt :</strong> {{ batiment }}</li>{% endif %}"
        "{% if ancien_resident %}<li><strong>Ancien résident :</strong> {{ ancien_resident }}</li>{% endif %}"
        "</ul>"
        "<p>Merci de préparer l'étiquette de boîte aux lettres correspondante.</p>"
        "<p>Cordialement,<br>Le Conseil Syndical</p>"
    )
    corps_texte = "Nouvel arrivant : {{ nom_complet }}. Merci de préparer l'étiquette BAL."

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO modele_email "
            "(code, libelle, sujet, corps_html, corps_texte, variables_disponibles, desactivable, actif) "
            "VALUES (:code, :libelle, :sujet, :corps_html, :corps_texte, :vars, 1, 1)"
        ),
        {
            "code": "nouvel_arrivant_bal",
            "libelle": "Nouvel arrivant — Étiquette boîte aux lettres",
            "sujet": "00213 - Nouvel arrivant MaJ Boites aux lettres",
            "corps_html": corps_html,
            "corps_texte": corps_texte,
            "vars": '["nom_complet", "batiment", "ancien_resident"]',
        },
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM modele_email WHERE code = 'nouvel_arrivant_bal'")
    )
