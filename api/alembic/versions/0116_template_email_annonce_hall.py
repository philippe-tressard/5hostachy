"""Ajout template email annonce_hall (annonce à afficher dans le hall).

Revision ID: 0116
Revises: 0115
Create Date: 2026-07-25
"""
from alembic import op
from sqlalchemy import text

revision = "0116"
down_revision = "0115"
branch_labels = None
depends_on = None

_CORPS_HTML = (
    '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">'
    "\U0001f4c4 Annonce à afficher dans le hall</h2>"
    '<p style="margin:0 0 16px">{{ auteur.prenom }} {{ auteur.nom }} a préparé une annonce pour '
    "<strong>{{ annonce.perimetre }}</strong>. Le PDF est en pièce jointe, prêt à imprimer "
    "au format <strong>{{ annonce.format }}</strong> et à afficher.</p>"
    '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
    '<td style="background:#F2EFE9;padding:16px;border-left:4px solid #C9983A">'
    '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">{{ annonce.perimetre }} · Format {{ annonce.format }} · {{ annonce.date }}</p>'
    '<p style="margin:0 0 8px;font-weight:700;font-size:17px;color:#1E3A5F">{{ annonce.titre }}</p>'
    '{% if annonce.apercu %}<p style="margin:0;font-size:14px;color:#5A6070">{{ annonce.apercu }}</p>{% endif %}'
    "</td></tr></table>"
    '<p style="margin:0 0 20px;font-size:13px;color:#5A6070">\U0001f4ce Pièce jointe : '
    "<strong>{{ annonce.fichier }}</strong> — imprimer en couleur, sans mise à l’échelle (100 %).</p>"
    '<p style="text-align:center;margin:0">'
    '<a href="{{ app.url }}/espace-cs?onglet=annonces-hall" '
    'style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">'
    "Voir l’historique des annonces</a></p>"
)


def upgrade():
    conn = op.get_bind()
    exists = conn.execute(
        text("SELECT 1 FROM modele_email WHERE code = 'annonce_hall'")
    ).fetchone()
    if not exists:
        conn.execute(
            text(
                "INSERT INTO modele_email (code, libelle, sujet, corps_html, corps_texte,"
                " variables_disponibles, actif, desactivable)"
                " VALUES (:code, :libelle, :sujet, :corps_html, :corps_texte, :variables, 1, 1)"
            ).bindparams(
                code="annonce_hall",
                libelle="Annonce hall (PDF à afficher)",
                sujet="\U0001f4c4 Annonce à afficher — {{ annonce.titre }} — {{ residence.nom }}",
                corps_html=_CORPS_HTML,
                corps_texte="",
                variables='["annonce", "auteur", "residence", "app"]',
            )
        )


def downgrade():
    op.get_bind().execute(text("DELETE FROM modele_email WHERE code = 'annonce_hall'"))
