"""Fusionner `sauvegarde_echec` et `alerte_espace_disque` en `alerte_systeme`.

Les deux modèles décrivaient un problème chacun, alors que le contrôle quotidien
(`health_monitor.run_health_check`) les découvre ensemble — base, WhatsApp,
sauvegardes, export hors site, disque — et n'envoie qu'un seul message. Deux
modèles pour un envoi ne se maintiennent pas : ils divergent.

Surtout, ni l'un ni l'autre n'était envoyé. `_send_alert` parlait à SMTP en
direct et fabriquait son HTML en f-strings, doublant le moteur d'envoi qui
existait à côté. L'alerte système — l'envoi le plus critique du produit — était
donc le seul qui n'apparaissait pas dans `historique_email`, n'était pas
modifiable depuis Admin → Emails, et ignorait `smtp_ssl_tls` en ne gérant que
STARTTLS.

Le nouveau modèle reprend la mise en page qui partait jusqu'ici, transposée en
Jinja : une boucle sur les problèmes, chacun avec son titre et ses précisions
techniques.

L'insertion est faite ici plutôt que laissée au seed, bien que le seed
l'insérerait au prochain démarrage : `send_email` se tait quand le modèle est
absent (`if not template: return`). Faire dépendre l'alerte système d'un seed
rejoué, c'est accepter qu'elle ne parte pas sans que personne ne l'apprenne.

Le corps vient de `seed.EMAIL_TEMPLATES` plutôt que d'être recopié — c'est le
pattern des migrations 0104 et 0108, qui évite d'entretenir deux copies du même
HTML.

Revision ID: 0129
Revises: 0128
Create Date: 2026-08-05
"""
import sqlalchemy as sa
from alembic import op

revision = "0129"
down_revision = "0128"
branch_labels = None
depends_on = None

_REMPLACES = ("sauvegarde_echec", "alerte_espace_disque")


def upgrade():
    conn = op.get_bind()

    from app.seed import EMAIL_TEMPLATES

    _code, libelle, sujet, corps_html, _desactivable = next(
        t for t in EMAIL_TEMPLATES if t[0] == "alerte_systeme"
    )
    conn.execute(
        sa.text(
            "INSERT OR IGNORE INTO modele_email "
            "(code, libelle, sujet, corps_html, corps_texte, "
            "variables_disponibles, desactivable, actif) "
            "VALUES ('alerte_systeme', :libelle, :sujet, :corps_html, "
            ":corps_texte, :variables, 0, 1)"
        ).bindparams(
            libelle=libelle,
            sujet=sujet,
            corps_html=corps_html,
            corps_texte=(
                "{{ nb_problemes }} problème(s) détecté(s) au contrôle du "
                "{{ date_controle }}."
            ),
            variables='["problemes", "nb_problemes", "date_controle"]',
        )
    )

    for code in _REMPLACES:
        conn.execute(
            sa.text("DELETE FROM modele_email WHERE code = :code").bindparams(code=code)
        )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM modele_email WHERE code = 'alerte_systeme'"))
    # Les deux modèles remplacés sont recréés dans leur dernier état connu.
    conn.execute(
        sa.text(
            "INSERT OR IGNORE INTO modele_email "
            "(code, libelle, sujet, corps_html, corps_texte, "
            "variables_disponibles, desactivable, actif) "
            "VALUES ('sauvegarde_echec', 'Échec sauvegarde', "
            "'ALERTE — Échec de la sauvegarde automatique', :corps, '', '', 0, 1)"
        ).bindparams(
            corps=(
                '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;'
                'color:#c0392b">⚠ Échec de la sauvegarde</h2>'
                '<p style="margin:0 0 12px">La sauvegarde automatique du '
                '<strong>{{ date }}</strong> a échoué.</p>'
                '<table role="presentation" style="width:100%;margin:0 0 12px;'
                'border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
                '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
                '<p style="margin:0;font-family:monospace;font-size:13px;color:#1A1A2E">'
                '{{ erreur }}</p>'
                '</td></tr></table>'
                '<p style="margin:0;color:#5A6070;font-size:13px">Veuillez vérifier la '
                'configuration des sauvegardes dans l’administration.</p>'
            )
        )
    )
    conn.execute(
        sa.text(
            "INSERT OR IGNORE INTO modele_email "
            "(code, libelle, sujet, corps_html, corps_texte, "
            "variables_disponibles, desactivable, actif) "
            "VALUES ('alerte_espace_disque', 'Alerte espace disque', "
            "'ALERTE — Espace disque faible ({{ pourcentage_libre }}% libre)', "
            ":corps, '', '', 0, 1)"
        ).bindparams(
            corps=(
                '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;'
                'color:#c0392b">⚠ Espace disque faible</h2>'
                '<p style="margin:0 0 12px">Le serveur ne dispose plus que de '
                '<strong>{{ pourcentage_libre }}%</strong> d’espace disque libre.</p>'
                '<table role="presentation" style="width:100%;margin:0 0 12px;'
                'border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
                '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
                '<p style="margin:0 0 4px;font-size:14px;color:#1A1A2E">'
                '<strong>Espace disponible :</strong> {{ espace_disponible }} sur '
                '{{ espace_total }}</p>'
                '</td></tr></table>'
                '<p style="margin:0;color:#5A6070;font-size:13px">Veuillez libérer de '
                'l’espace sur le serveur (images Docker, backups, logs…) ou étendre le '
                'stockage.</p>'
            )
        )
    )
