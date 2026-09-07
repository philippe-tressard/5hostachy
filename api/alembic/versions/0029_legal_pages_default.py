"""Pages légales — pré-remplissage mentions_legales et politique_confidentialite.

Revision ID: 0029
Revises: 0028
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None

MENTIONS_LEGALES = (
    '<h2>Éditeur du service</h2>'
    '<p><strong>5Hostachy</strong><br>Application de gestion de copropriété — déployée en mode auto-hébergé.<br>'
    "L'identité de l'éditeur correspond à la copropriété ou au syndic bénévole qui gère cette instance.</p>"
    '<h2>Directeur de la publication</h2>'
    "<p>Le directeur de la publication est l'administrateur désigné de l'instance.</p>"
    '<h2>Hébergeur</h2>'
    "<p>Cette application est auto-hébergée. L'hébergeur est l'organisation ou la personne physique "
    "administrant le serveur sur lequel l'instance est déployée.</p>"
    '<h2>Propriété intellectuelle</h2>'
    '<p>Le code source de 5Hostachy est distribué sous licence <a href="https://spdx.org/licenses/MIT.html" target="_blank" rel="noopener noreferrer">MIT</a> (voir le fichier LICENSE du dépôt). '
    "Les contenus publiés dans l'application restent la propriété de leurs auteurs respectifs.</p>"
    '<h2>Responsabilité</h2>'
    "<p>L'éditeur s'efforce de fournir des informations exactes et à jour. Il ne saurait être tenu responsable "
    'des erreurs ou omissions dans les informations diffusées.</p>'
    '<h2>Contact</h2>'
    "<p>Pour toute question, contactez l'administrateur via la messagerie interne.</p>"
)

POLITIQUE_CONFIDENTIALITE = (
    '<h2>1. Responsable du traitement</h2>'
    "<p>Le responsable du traitement est l'administrateur de cette instance 5Hostachy "
    '(syndic bénévole ou conseil syndical). Toute demande relative à vos données peut lui être adressée '
    "via la messagerie de l'application.</p>"
    '<h2>2. Données collectées</h2>'
    "<ul><li><strong>Données d'identification\u00a0:</strong> nom, prénom, adresse e-mail, téléphone (facultatif).</li>"
    '<li><strong>Données de résidence\u00a0:</strong> lot(s) associé(s), bâtiment, tantièmes.</li>'
    "<li><strong>Données d'usage\u00a0:</strong> tickets soumis, messages échangés, documents téléchargés.</li>"
    "<li><strong>Données techniques\u00a0:</strong> tokens d'authentification (cookies HttpOnly), date de connexion.</li></ul>"
    '<h2>3. Finalités et bases légales</h2>'
    '<ul><li><strong>Gestion de la copropriété</strong> — base\u00a0: intérêt légitime (art.\u00a06-1-f).</li>'
    '<li><strong>Authentification et sécurité</strong> — base\u00a0: intérêt légitime (art.\u00a06-1-f).</li>'
    '<li><strong>Communication résidents/CS</strong> — base\u00a0: exécution du contrat (art.\u00a06-1-b).</li>'
    '<li><strong>E-mails transactionnels</strong> — base\u00a0: intérêt légitime / consentement.</li></ul>'
    '<h2>4. Destinataires</h2>'
    "<p>Les données sont accessibles uniquement aux membres du conseil syndical et à l'administrateur. "
    'Elles ne sont pas transférées à des tiers ni commercialisées. Aucun transfert hors UE.</p>'
    '<h2>5. Durée de conservation</h2>'
    '<ul><li>Données de compte actif\u00a0: durée de la relation + 2 ans.</li>'
    '<li>Tokens de rafraîchissement\u00a0: 7 jours glissants.</li>'
    '<li>Sauvegardes\u00a0: selon la configuration.</li></ul>'
    '<h2>6. Vos droits</h2>'
    "<p>Conformément au RGPD vous disposez des droits d'accès (art.\u00a015), rectification (art.\u00a016), "
    'effacement (art.\u00a017), portabilité (art.\u00a020), opposition (art.\u00a021) et retrait du consentement (art.\u00a07-3). '
    "Contactez l'administrateur via la messagerie. En cas de litige\u00a0: <strong>CNIL</strong> — www.cnil.fr.</p>"
    '<h2>7. Cookies</h2>'
    "<p>L'application utilise exclusivement des cookies techniques d'authentification "
    '(<code>access_token</code>, <code>refresh_token</code>) définis en '
    '<code>HttpOnly; Secure; SameSite=Strict</code>. Aucun cookie publicitaire ou de traçage.</p>'
)


def upgrade():
    conn = op.get_bind()
    for cle, valeur in [
        ('mentions_legales', MENTIONS_LEGALES),
        ('politique_confidentialite', POLITIQUE_CONFIDENTIALITE),
    ]:
        existing = conn.execute(
            sa.text('SELECT cle FROM config_site WHERE cle = :cle'),
            {'cle': cle},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text('INSERT INTO config_site (cle, valeur) VALUES (:cle, :valeur)'),
                {'cle': cle, 'valeur': valeur},
            )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM config_site WHERE cle IN ('mentions_legales', 'politique_confidentialite')")
    )
