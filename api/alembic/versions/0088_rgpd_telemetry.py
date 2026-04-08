"""RGPD télémétrie : champ opt_out_telemetrie + mise à jour politique de confidentialité.

Revision ID: 0088
Revises: 0087
Create Date: 2026-04-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None

# ── Paragraphes à ajouter à la politique de confidentialité ──────────────────

TELEMETRY_DATA_CLAUSE = (
    '<li><strong>Données de navigation\u00a0:</strong> pages visitées, actions effectuées '
    '(anonymisées après 30\u00a0jours). Ces données sont collectées sur la base de '
    "l'intérêt légitime (art.\u00a06-1-f) afin d'améliorer le service. "
    "Vous pouvez désactiver cette collecte à tout moment depuis votre profil.</li>"
)

TELEMETRY_LEGAL_BASIS = (
    '<li><strong>Télémétrie d\'usage</strong> — base\u00a0: intérêt légitime (art.\u00a06-1-f). '
    'Droit d\'opposition exerçable via le profil utilisateur (opt-out).</li>'
)

TELEMETRY_RETENTION = (
    '<li>Télémétrie détaillée (avec identifiant)\u00a0: 30\u00a0jours.</li>'
    '<li>Télémétrie agrégée quotidienne (anonyme)\u00a0: 12\u00a0mois.</li>'
    '<li>Télémétrie agrégée mensuelle (anonyme)\u00a0: 10\u00a0ans.</li>'
)

TELEMETRY_COOKIE = (
    " L'application collecte également des statistiques de navigation anonymisées "
    "(pages visitées) pour améliorer le service. Cette collecte peut être désactivée "
    "dans votre profil."
)


def upgrade():
    # 1. Ajouter le champ opt_out_telemetrie sur utilisateur
    with op.batch_alter_table("utilisateur") as batch_op:
        batch_op.add_column(
            sa.Column("opt_out_telemetrie", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    # 2. Mettre à jour la politique de confidentialité
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT valeur FROM config_site WHERE cle = 'politique_confidentialite'"),
    ).fetchone()

    if row:
        html = row[0]

        # 2a. Section "Données collectées" — ajouter les données de navigation
        old_tech = "<li><strong>Données techniques"
        if old_tech in html and "Données de navigation" not in html:
            html = html.replace(old_tech, TELEMETRY_DATA_CLAUSE + old_tech)

        # 2b. Section "Finalités et bases légales" — ajouter la télémétrie
        old_email = "<li><strong>E-mails transactionnels"
        if old_email in html and "Télémétrie" not in html:
            html = html.replace(old_email, TELEMETRY_LEGAL_BASIS + old_email)

        # 2c. Section "Durée de conservation" — ajouter les durées télémétrie
        old_sauvegarde = "<li>Sauvegardes"
        if old_sauvegarde in html and "Télémétrie détaillée" not in html:
            html = html.replace(old_sauvegarde, TELEMETRY_RETENTION + old_sauvegarde)

        # 2d. Section "Cookies" — mentionner la télémétrie opt-out
        old_aucun = "Aucun cookie publicitaire ou de traçage."
        if old_aucun in html and "statistiques de navigation" not in html:
            html = html.replace(old_aucun, old_aucun + TELEMETRY_COOKIE)

        conn.execute(
            sa.text("UPDATE config_site SET valeur = :val WHERE cle = 'politique_confidentialite'"),
            {"val": html},
        )


def downgrade():
    with op.batch_alter_table("utilisateur") as batch_op:
        batch_op.drop_column("opt_out_telemetrie")

    # On ne tente pas de reverter le texte de la politique (trop fragile)
