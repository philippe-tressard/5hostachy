"""Retirer les huit modèles d'e-mail qu'aucun code n'envoie.

Audit des modèles d'e-mail (volet 1, demandé le 01/08/2026). Sur trente modèles
en base, huit n'avaient **aucun** point d'appel : ni `send_email(code=…)`, ni
appel dynamique, ni tâche planifiée — vérifié sur tout le dépôt, pas seulement
sur `app/`.

La leçon des `vigik_*` (v2.31.2) impose une contre-épreuve avant de conclure :
un modèle sans point d'appel peut signaler un **envoi oublié**, pas un modèle
mort. Chacun a donc été confronté au manuel utilisateur et à l'interface :

- `invitation_resident` — aucun parcours d'invitation n'existe ; l'entrée se
  fait par auto-inscription puis validation (`compte_en_attente`).
- `locataire_validation_demande`, `locataire_valide`, `locataire_refuse` —
  l'espace bailleur gère les baux et les locataires en saisie directe. Aucun
  compte locataire n'est soumis à la validation d'un propriétaire.
- `ticket_cree_cs` — la création d'un ticket notifie déjà le conseil syndical
  **dans l'application** (`Notification` de type `ticket_update`). Le manuel ne
  promet pas d'e-mail à la création, et la préférence « Mises à jour de mes
  tickets » porte sur les suites (statut, messages), qui sont bien envoyées.
- `ticket_urgence_bailleur` — un ticket urgent lève une notification `urgente`
  dans l'application ; rien nulle part ne promet d'e-mail au bailleur.
- `digest_quotidien`, `digest_hebdomadaire` — aucun travail périodique de
  digest n'existe, ni dans APScheduler ni en cron, et le manuel n'en parle pas.

`document_publie` a suivi le chemin inverse et n'est PAS supprimé : le manuel
recommande « documents = e-mail » et le profil propose la case. C'est un envoi
manquant, traité à part.

Aucune clé étrangère ne vise `modele_email` : `historique_email.code` est un
champ texte libre. Les envois passés restent donc lisibles, avec leur code
d'origine — c'est le comportement voulu.

Le `downgrade` recrée les huit modèles à l'identique de leur dernier état connu.

Revision ID: 0127
Revises: 0126
Create Date: 2026-08-05
"""
from alembic import op
from sqlalchemy import text

revision = "0127"
down_revision = "0126"
branch_labels = None
depends_on = None

CODES_MORTS = (
    "invitation_resident",
    "locataire_validation_demande",
    "locataire_valide",
    "locataire_refuse",
    "ticket_cree_cs",
    "ticket_urgence_bailleur",
    "digest_quotidien",
    "digest_hebdomadaire",
)

# État restauré par le downgrade. Repris de `seed.EMAIL_TEMPLATES` avant
# suppression : c'est la seule copie qui subsistera une fois la liste nettoyée.
MODELES_RESTAURES = [
    (
        "invitation_resident",
        "Invitation résident",
        "Bienvenue sur {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Bienvenue, {{ destinataire.prenom }} !</h2>'
        '<p style="margin:0 0 12px">Vous avez été invité(e) à rejoindre l’espace numérique de <strong>{{ residence.nom }}</strong>.</p>'
        '<p style="margin:0 0 24px;color:#5A6070">Créez votre compte en quelques clics pour accéder aux documents, au calendrier, aux tickets et à toutes les informations de votre résidence.</p>'
        '<p style="text-align:center;margin:0 0 8px"><a href="{{ lien }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Créer mon compte</a></p>',
        0,
    ),
    (
        "locataire_validation_demande",
        "Demande validation locataire",
        "Un locataire souhaite s'inscrire sur votre lot — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Validation de locataire requise</h2>'
        '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
        '<p style="margin:0 0 12px"><strong>{{ locataire.prenom }} {{ locataire.nom }}</strong> souhaite s’inscrire en tant que locataire de votre lot <strong>{{ lot.numero }}</strong>.</p>'
        '<p style="margin:0 0 24px;color:#5A6070">Connectez-vous à l’application pour valider ou refuser cette demande.</p>'
        '<p style="text-align:center;margin:0"><a href="{{ app.url }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Gérer la demande</a></p>',
        1,
    ),
    (
        "locataire_valide",
        "Locataire validé",
        "Votre inscription a été validée — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Inscription validée !</h2>'
        '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
        '<p style="margin:0 0 24px">Votre inscription en tant que locataire a été validée. Vous pouvez maintenant accéder à l’ensemble des services de la résidence.</p>'
        '<p style="text-align:center;margin:0"><a href="{{ app.url }}" style="display:inline-block;background:#3D6B4F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Accéder à l’application</a></p>',
        1,
    ),
    (
        "locataire_refuse",
        "Locataire refusé",
        "Votre inscription n'a pas été acceptée — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Inscription non acceptée</h2>'
        '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
        '<p style="margin:0 0 12px">Votre demande d’inscription en tant que locataire n’a pas été acceptée.</p>'
        '<p style="margin:0;color:#5A6070">Contactez votre propriétaire ou le conseil syndical pour plus d’informations.</p>',
        1,
    ),
    (
        "ticket_cree_cs",
        "Ticket créé (CS)",
        "Nouveau ticket #{{ ticket.numero }} — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Nouveau ticket soumis</h2>'
        '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
        '<td style="background:#F2EFE9;padding:16px">'
        '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #{{ ticket.numero }}</p>'
        '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
        '<p style="margin:0;font-size:14px;color:#5A6070">par {{ auteur.prenom }} {{ auteur.nom }}</p>'
        '</td></tr></table>'
        '<p style="text-align:center;margin:0"><a href="{{ app.url }}/tickets/{{ ticket.id }}" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir le ticket</a></p>',
        1,
    ),
    (
        "ticket_urgence_bailleur",
        "Ticket urgence (bailleur)",
        "URGENT — Ticket sur votre lot {{ lot.numero }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#c0392b">\U0001f6a8 Ticket URGENT</h2>'
        '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
        '<p style="margin:0 0 16px">Un ticket <strong style="color:#c0392b">URGENT</strong> a été soumis concernant votre lot <strong>{{ lot.numero }}</strong> :</p>'
        '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
        '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
        '<p style="margin:0;font-weight:700;font-size:16px;color:#1A1A2E">{{ ticket.titre }}</p>'
        '</td></tr></table>',
        1,
    ),
    (
        "digest_quotidien",
        "Digest quotidien",
        "Résumé du jour — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">☀️ Votre résumé quotidien</h2>'
        '<p style="margin:0 0 16px">Bonjour {{ destinataire.prenom }}, voici les dernières actualités de votre résidence.</p>'
        '<hr style="border:none;border-top:1px solid #D0D8E4;margin:0 0 16px">',
        1,
    ),
    (
        "digest_hebdomadaire",
        "Digest hebdomadaire",
        "Résumé de la semaine — {{ residence.nom }}",
        '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4ca Résumé de la semaine</h2>'
        '<p style="margin:0 0 16px">Bonjour {{ destinataire.prenom }}, voici un récapitulatif de la semaine écoulée sur votre résidence.</p>'
        '<hr style="border:none;border-top:1px solid #D0D8E4;margin:0 0 16px">',
        1,
    ),
]


def upgrade():
    conn = op.get_bind()
    for code in CODES_MORTS:
        conn.execute(
            text("DELETE FROM modele_email WHERE code = :code").bindparams(code=code)
        )


def downgrade():
    conn = op.get_bind()
    for code, libelle, sujet, corps_html, desactivable in MODELES_RESTAURES:
        deja = conn.execute(
            text("SELECT 1 FROM modele_email WHERE code = :code").bindparams(code=code)
        ).fetchone()
        if deja:
            continue
        conn.execute(
            text(
                "INSERT INTO modele_email "
                "(code, libelle, sujet, corps_html, corps_texte, "
                "variables_disponibles, desactivable, actif) "
                "VALUES (:code, :libelle, :sujet, :corps_html, '', '', "
                ":desactivable, 1)"
            ).bindparams(
                code=code,
                libelle=libelle,
                sujet=sujet,
                corps_html=corps_html,
                desactivable=desactivable,
            )
        )
