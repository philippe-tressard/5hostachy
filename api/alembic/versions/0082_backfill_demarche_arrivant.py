"""Backfill demarche_arrivant pour les utilisateurs ayant déjà déclaré via notification

Revision ID: 0082
Revises: 0081
Create Date: 2026-04-01
"""
from alembic import op
from sqlalchemy import text

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade():
    # Les utilisateurs ayant la notification "Bienvenue dans la résidence !"
    # ont déjà fait la démarche nouvel arrivant via l'ancien système
    op.execute(
        text(
            "UPDATE utilisateur SET demarche_arrivant = 'nouvel_arrivant' "
            "WHERE demarche_arrivant IS NULL "
            "AND id IN (SELECT destinataire_id FROM notification WHERE titre = 'Bienvenue dans la résidence !')"
        )
    )


def downgrade():
    pass
