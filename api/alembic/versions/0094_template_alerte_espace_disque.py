"""Ajout template email alerte_espace_disque.

Revision ID: 0094
Revises: 0093
Create Date: 2026-04-14
"""
from alembic import op
from sqlalchemy import text

revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    exists = conn.execute(text("SELECT 1 FROM modele_email WHERE code = 'alerte_espace_disque'")).fetchone()
    if not exists:
        conn.execute(text("""
            INSERT INTO modele_email (code, libelle, sujet, corps_html, corps_texte, actif, desactivable)
            VALUES (
                'alerte_espace_disque',
                'Alerte espace disque',
                'ALERTE — Espace disque faible ({{ pourcentage_libre }}% libre)',
                '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#c0392b">⚠ Espace disque faible</h2>'
                || '<p style="margin:0 0 12px">Le serveur ne dispose plus que de <strong>{{ pourcentage_libre }}%</strong> d''espace disque libre.</p>'
                || '<table role="presentation" style="width:100%;margin:0 0 12px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
                || '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
                || '<p style="margin:0 0 4px;font-size:14px;color:#1A1A2E"><strong>Espace disponible :</strong> {{ espace_disponible }} sur {{ espace_total }}</p>'
                || '</td></tr></table>'
                || '<p style="margin:0;color:#5A6070;font-size:13px">Veuillez libérer de l''espace sur le serveur (images Docker, backups, logs…) ou étendre le stockage.</p>',
                '',
                1,
                0
            )
        """))


def downgrade():
    op.get_bind().execute(text("DELETE FROM modele_email WHERE code = 'alerte_espace_disque'"))
