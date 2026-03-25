"""0067 — FAQ : entrée groupe WhatsApp 5Hostachy

Revision ID: 0067
Revises: 0066
Create Date: 2026-03-21
"""

revision = '0067'
down_revision = '0066'
branch_labels = None
depends_on = None

from alembic import op
from sqlalchemy import text

CAT = "📱 Application & Numérique"

QUESTION = "Y a-t-il un groupe WhatsApp pour la résidence ?"
REPONSE = (
    "Oui, un groupe WhatsApp **5Hostachy** a été créé comme canal d'information de la résidence "
    "5 boulevard Fernand Hostachy à Croissy-sur-Seine.\n\n"
    "Ce groupe ne se substitue pas au Conseil Syndical, au syndic IFF Gestion ni aux informations "
    "disponibles dans le hall de chaque bâtiment. Il permet d'être plus agile pour informer les "
    "résidents au fil de l'eau sur les dossiers en cours.\n\n"
    "Seuls les membres du Conseil Syndical peuvent poster des messages dans ce groupe.\n\n"
    "Lien d'invitation : https://chat.whatsapp.com/FyBjmFwTH5eA5BJcXkmjFj"
)
ORDRE = 66


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        text("SELECT 1 FROM faq_item WHERE categorie = :cat AND question = :q"),
        {"cat": CAT, "q": QUESTION}
    ).fetchone()
    if not exists:
        op.execute(
            text(
                "INSERT INTO faq_item (categorie, question, reponse, ordre, actif, cree_le, mis_a_jour_le) "
                "VALUES (:cat, :q, :r, :o, 1, datetime('now'), datetime('now'))"
            ).bindparams(cat=CAT, q=QUESTION, r=REPONSE, o=ORDRE)
        )


def downgrade() -> None:
    op.execute(
        text("DELETE FROM faq_item WHERE categorie = :cat AND question = :q")
        .bindparams(cat=CAT, q=QUESTION)
    )
