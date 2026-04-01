"""Ajout demarche_arrivant + préférences notifications JSON en base utilisateur

Revision ID: 0081
Revises: 0080
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None

# Valeur par défaut JSON pour les préférences de notifications
DEFAULT_PREFS = '{"ticket_app":true,"ticket_mail":true,"actu_app":true,"actu_mail":true,"doc_app":true,"doc_mail":false}'


def upgrade():
    # 1. Ajout colonne demarche_arrivant (nullable)
    op.add_column("utilisateur", sa.Column("demarche_arrivant", sa.String(), nullable=True))

    # 2. Transformation preferences_notifications : "realtime" → JSON complet
    op.execute(
        f"UPDATE utilisateur SET preferences_notifications = '{DEFAULT_PREFS}' "
        "WHERE preferences_notifications IS NULL OR preferences_notifications IN ('realtime', 'digest_daily', 'digest_weekly', '')"
    )


def downgrade():
    op.drop_column("utilisateur", "demarche_arrivant")
    op.execute("UPDATE utilisateur SET preferences_notifications = 'realtime'")
