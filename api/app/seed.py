"""
Seeding initial — données de démarrage (à exécuter une seule fois).
Lance avec : python -m app.seed
"""
import json
from datetime import date

from sqlmodel import Session, select

from app.database import engine, create_db_and_tables
from app.auth.jwt import hash_password
from app.models.core import (
    Copropriete, Batiment, Utilisateur, StatutUtilisateur, RoleUtilisateur,
    ProfilAccesDocument, CategorieDocument, ConfigSauvegarde,
    ModeleEmail, FaqItem, ConfigSite, DiagnosticType,
)


PROFILS = [
    {
        "code": "résidence_tous",
        "libelle": "Tous les résidents",
        "description": "Copropriétaires, bailleurs, locataires",
        "roles_autorises": json.dumps(["propriétaire", "résident"]),
        "require_cs": True,
    },
    {
        "code": "copropriétaires_et_cs",
        "libelle": "Copropriétaires et CS",
        "description": "Propriétaires uniquement — exclut les locataires",
        "roles_autorises": json.dumps(["propriétaire"]),
        "require_cs": True,
    },
    {
        "code": "cs_syndic_uniquement",
        "libelle": "CS et syndic uniquement",
        "description": "Conseil syndical, syndic et admin uniquement",
        "roles_autorises": json.dumps(["syndic"]),  # statut syndic ; CS bypassé en amont
        "require_cs": True,
    },
    {
        "code": "lot_occupants",
        "libelle": "Occupants du lot",
        "description": "Propriétaire + locataire actif du lot + CS + syndic",
        "roles_autorises": json.dumps(["propriétaire", "résident"]),
        "require_cs": True,
    },
    {
        "code": "lot_propriétaires",
        "libelle": "Propriétaires du lot",
        "description": "Propriétaire du lot uniquement + CS + syndic — exclut le locataire",
        "roles_autorises": json.dumps(["propriétaire"]),
        "require_cs": True,
    },
]

CATEGORIES = [
    ("reglement_copropriete", "Règlement de copropriété", "résidence_tous", "résidence", False),
    ("pv_ag",               "PV d'Assemblée Générale",  "résidence_tous", "bâtiment",  True),
    ("fiche_synthetique",   "Fiche synthétique annuelle",  "résidence_tous",   "résidence", False),
    ("plan_residence",      "Plan de la résidence",        "résidence_tous",   "résidence", False),
    ("attestation_lot",     "Attestation (lot)",           "lot_occupants",    "lot",        True),
    ("diagnostic_lot",      "Diagnostic",                  "copropriétaires_et_cs", "bâtiment", True),
    ("contrat_fournisseur", "Contrat fournisseur",         "copropriétaires_et_cs", "bâtiment", True),
    ("contrat_assurance",   "Contrat assurance",           "copropriétaires_et_cs", "résidence", True),
    ("devis_travaux",       "Devis travaux",               "cs_syndic_uniquement", "bâtiment", True),
    ("document_interne_cs", "Document interne CS",         "cs_syndic_uniquement", "résidence", False),
]

# ── Contenus légaux par défaut (réutilisé par config.py si absent en BDD) ──
DEFAULT_LEGAL = {
    'mentions_legales': (
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
    ),
    'politique_confidentialite': (
        '<h2>1. Responsable du traitement</h2>'
        "<p>Le responsable du traitement est l'administrateur de cette instance 5Hostachy "
        '(syndic bénévole ou conseil syndical). Toute demande relative à vos données peut lui être adressée '
        "via la messagerie de l'application.</p>"
        '<h2>2. Données collectées</h2>'
        "<ul><li><strong>Données d'identification\u00a0:</strong> nom, prénom, adresse e-mail, téléphone (facultatif).</li>"
        '<li><strong>Données de résidence\u00a0:</strong> lot(s) associé(s), bâtiment, tantièmes.</li>'
        '<li><strong>Données d\'usage\u00a0:</strong> tickets soumis, messages échangés, documents téléchargés.</li>'
        '<li><strong>Données techniques\u00a0:</strong> tokens d\'authentification (cookies HttpOnly), date de connexion.</li></ul>'
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
        '<p>Conformément au RGPD vous disposez des droits d\'accès (art.\u00a015), rectification (art.\u00a016), '
        'effacement (art.\u00a017), portabilité (art.\u00a020), opposition (art.\u00a021) et retrait du consentement (art.\u00a07-3). '
        "Contactez l'administrateur via la messagerie. En cas de litige\u00a0: <strong>CNIL</strong> — www.cnil.fr.</p>"
        '<h2>7. Cookies</h2>'
        "<p>L'application utilise exclusivement des cookies techniques d'authentification "
        '(<code>access_token</code>, <code>refresh_token</code>) définis en '
        '<code>HttpOnly; Secure; SameSite=Strict</code>. Aucun cookie publicitaire ou de traçage.</p>'
    ),
}

EMAIL_TEMPLATES = [
    # ── Styles inline mutualisés (CTA = Call-to-action button) ──
    # Les templates sont encapsulés dans le gabarit email.py (_wrap_email)
    # => pas besoin de <html>/<body>, juste le contenu riche.

    ("invitation_resident", "Invitation résident", "Bienvenue sur {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Bienvenue, {{ destinataire.prenom }}\u202f!</h2>'
     '<p style="margin:0 0 12px">Vous avez été invité(e) à rejoindre l\u2019espace numérique de <strong>{{ residence.nom }}</strong>.</p>'
     '<p style="margin:0 0 24px;color:#5A6070">Créez votre compte en quelques clics pour accéder aux documents, au calendrier, aux tickets et à toutes les informations de votre résidence.</p>'
     '<p style="text-align:center;margin:0 0 8px"><a href="{{ lien }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Créer mon compte</a></p>',
     False),

    ("reinitialisation_mdp", "Réinitialisation mot de passe", "Réinitialisation de votre mot de passe — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Réinitialisation de votre mot de passe</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 24px">Une demande de réinitialisation a été effectuée pour votre compte. Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe.</p>'
     '<p style="text-align:center;margin:0 0 16px"><a href="{{ lien }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Réinitialiser mon mot de passe</a></p>'
     '<p style="margin:0;font-size:13px;color:#5A6070">Ce lien est valable <strong>1 heure</strong>. Si vous n\u2019avez pas fait cette demande, ignorez cet e-mail.</p>',
     False),

    ("compte_en_attente", "Compte en attente", "Nouvelle demande de compte — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Nouvelle demande de compte</h2>'
     '<p style="margin:0 0 12px">Un nouveau résident souhaite rejoindre la résidence\u202f:</p>'
     '<table role="presentation" style="margin:0 0 20px;border-left:4px solid #C9983A;padding-left:16px"><tr><td>'
     '<p style="margin:0 0 4px;font-weight:600;font-size:16px">{{ utilisateur.prenom }} {{ utilisateur.nom }}</p>'
     '<p style="margin:0;color:#5A6070">{{ utilisateur.email }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/admin/utilisateurs" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Valider le compte</a></p>',
     True),

    ("compte_active", "Compte activé", "Votre compte est activé — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Votre compte est activé\u202f!</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 24px">Votre compte sur <strong>{{ residence.nom }}</strong> est maintenant actif. Vous pouvez dès à présent accéder à l\u2019ensemble des services de votre résidence.</p>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}" style="display:inline-block;background:#3D6B4F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Accéder à l\u2019application</a></p>',
     True),

    ("compte_refuse", "Compte refusé", "Votre demande de compte — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Demande de compte non acceptée</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 12px">Votre demande de création de compte sur <strong>{{ residence.nom }}</strong> n\u2019a pas pu être acceptée.</p>'
     '<p style="margin:0;color:#5A6070">Si vous pensez qu\u2019il s\u2019agit d\u2019une erreur, n\u2019hésitez pas à contacter le conseil syndical.</p>',
     True),

    ("locataire_validation_demande", "Demande validation locataire", "Un locataire souhaite s'inscrire sur votre lot — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Validation de locataire requise</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 12px"><strong>{{ locataire.prenom }} {{ locataire.nom }}</strong> souhaite s\u2019inscrire en tant que locataire de votre lot <strong>{{ lot.numero }}</strong>.</p>'
     '<p style="margin:0 0 24px;color:#5A6070">Connectez-vous à l\u2019application pour valider ou refuser cette demande.</p>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Gérer la demande</a></p>',
     True),

    ("locataire_valide", "Locataire validé", "Votre inscription a été validée — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Inscription validée\u202f!</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 24px">Votre inscription en tant que locataire a été validée. Vous pouvez maintenant accéder à l\u2019ensemble des services de la résidence.</p>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}" style="display:inline-block;background:#3D6B4F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Accéder à l\u2019application</a></p>',
     True),

    ("locataire_refuse", "Locataire refusé", "Votre inscription n'a pas été acceptée — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Inscription non acceptée</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 12px">Votre demande d\u2019inscription en tant que locataire n\u2019a pas été acceptée.</p>'
     '<p style="margin:0;color:#5A6070">Contactez votre propriétaire ou le conseil syndical pour plus d\u2019informations.</p>',
     True),

    ("ticket_cree_cs", "Ticket créé (CS)", "Nouveau ticket #{{ ticket.numero }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Nouveau ticket soumis</h2>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #{{ ticket.numero }}</p>'
     '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
     '<p style="margin:0;font-size:14px;color:#5A6070">par {{ auteur.prenom }} {{ auteur.nom }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/tickets/{{ ticket.id }}" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir le ticket</a></p>',
     True),

    ("ticket_bug_admin", "Ticket bug — notification admin site", "Bug signalé via Tickets — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#c0392b">\u26a0 Bug signalé</h2>'
     '<p style="margin:0 0 12px">Un ticket de type <strong style="color:#c0392b">Bug</strong> a été soumis par <strong>{{ auteur.prenom }} {{ auteur.nom }}</strong>{% if auteur.email %} (<a href="mailto:{{ auteur.email }}" style="color:#1E3A5F">{{ auteur.email }}</a>){% endif %}.</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
     '<p style="margin:0 0 4px;font-weight:700;font-size:16px;color:#1A1A2E">{{ ticket.titre }}</p>'
     '<p style="margin:0;font-size:14px;color:#5A6070">{{ ticket.description }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/tickets/{{ ticket.id }}" style="display:inline-block;background:#c0392b;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Traiter le bug</a></p>',
     True),

    ("ticket_syndic", "Ticket transmis au syndic", "{% if reference_copro %}\U0001f3e2 {{ reference_copro }} — {% endif %}Ticket #{{ ticket.numero }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4cb Ticket transmis par le conseil syndical</h2>'
     '<p style="margin:0 0 16px">Un ticket a été transmis à votre attention par le conseil syndical de <strong>{{ residence.nom }}</strong>{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #{{ ticket.numero }}{% if ticket.categorie %} \u00b7 {{ ticket.categorie }}{% endif %}</p>'
     '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
     '<p style="margin:0 0 8px;font-size:14px;color:#1A1A2E">{{ ticket.description }}</p>'
     '<p style="margin:0;font-size:14px;color:#5A6070">Soumis par {{ auteur.prenom }} {{ auteur.nom }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/tickets/{{ ticket.id }}" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Consulter le ticket</a></p>',
     True),

    ("ticket_statut_change", "Statut ticket modifié", "Ticket #{{ ticket.numero }} mis à jour — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Mise à jour de votre ticket</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 16px">Le statut de votre ticket a été mis à jour\u202f:</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Ticket #{{ ticket.numero }}</p>'
     '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ ticket.titre }}</p>'
     '<p style="margin:0"><span style="display:inline-block;background:#3D6B4F;color:#fff;padding:4px 12px;border-radius:4px;font-size:13px;font-weight:600">{{ ticket.statut }}</span></p>'
     '</td></tr></table>',
     True),

    ("ticket_nouveau_message", "Nouveau message sur un ticket", "Nouveau message — Ticket #{{ ticket.numero }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">💬 Nouveau message sur votre ticket</h2>'
     '<p style="margin:0 0 16px">Un nouveau message a été ajouté sur le ticket <strong>#{{ ticket.numero }} — {{ ticket.titre }}</strong> par {{ auteur_action.prenom }} {{ auteur_action.nom }}\u202f:</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0;font-size:14px;color:#1A1A2E">{{ message.contenu }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/tickets/{{ ticket.id }}" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir le ticket</a></p>',
     True),

    ("ticket_urgence_bailleur", "Ticket urgence (bailleur)", "URGENT — Ticket sur votre lot {{ lot.numero }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#c0392b">\U0001f6a8 Ticket URGENT</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 16px">Un ticket <strong style="color:#c0392b">URGENT</strong> a été soumis concernant votre lot <strong>{{ lot.numero }}</strong>\u202f:</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
     '<p style="margin:0;font-weight:700;font-size:16px;color:#1A1A2E">{{ ticket.titre }}</p>'
     '</td></tr></table>',
     True),

    ("vigik_commande_recue", "Commande vigik reçue (CS)", "Nouvelle commande de {{ type }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Nouvelle demande de badge/clé</h2>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 4px;font-size:13px;color:#5A6070">Type : {{ type }} · Lot {{ lot.numero }}</p>'
     '<p style="margin:0;font-weight:700;font-size:16px;color:#1E3A5F">{{ demandeur.prenom }} {{ demandeur.nom }}</p>'
     '</td></tr></table>',
     True),

    ("vigik_accepte", "Commande vigik acceptée", "Votre demande de {{ type }} a été acceptée — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#3D6B4F">\u2705 Demande acceptée</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0">Votre demande de <strong>{{ type }}</strong> a été acceptée. Vous serez informé(e) de la suite à donner.</p>',
     True),

    ("vigik_refuse", "Commande vigik refusée", "Votre demande de {{ type }} n'a pas été acceptée — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Demande non acceptée</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 8px">Votre demande de <strong>{{ type }}</strong> n\u2019a pas été acceptée.</p>'
     '<p style="margin:0;color:#5A6070"><strong>Motif\u202f:</strong> {{ motif }}</p>',
     True),

    ("calendrier_evenement_cree", "Événement calendrier créé", "Nouvel événement : {{ evenement.titre }} — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4c5 Nouvel événement</h2>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 4px;font-size:13px;color:#C9983A;font-weight:600">{{ evenement.date }}</p>'
     '<p style="margin:0;font-weight:700;font-size:16px;color:#1E3A5F">{{ evenement.titre }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/calendrier" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir le calendrier</a></p>',
     True),

    ("document_publie", "Document publié", "Nouveau document disponible — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4c4 Nouveau document</h2>'
     '<p style="margin:0 0 16px">Un nouveau document a été publié sur l\u2019espace de votre résidence\u202f:</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0;font-weight:700;font-size:16px;color:#1E3A5F">{{ document.titre }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/documents" style="display:inline-block;background:#3D6B4F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Consulter les documents</a></p>',
     True),

    ("publication_syndic", "Publication transmise au syndic", "{% if reference_copro %}\U0001f3e2 {{ reference_copro }} — {% endif %}Nouvelle publication — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4e2 Publication du conseil syndical</h2>'
     '<p style="margin:0 0 16px">Une publication a été transmise à votre attention par le conseil syndical de <strong>{{ residence.nom }}</strong>{% if reference_copro %} — réf. {{ reference_copro }}{% endif %}.</p>'
     '<table role="presentation" style="width:100%;margin:0 0 20px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#F2EFE9;padding:16px">'
     '<p style="margin:0 0 8px;font-weight:700;font-size:16px;color:#1E3A5F">{{ publication.titre }}</p>'
     '<p style="margin:0;font-size:14px;color:#1A1A2E">{{ publication.extrait }}</p>'
     '</td></tr></table>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/actualites" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Voir la publication</a></p>',
     True),

    ("digest_quotidien", "Digest quotidien", "Résumé du jour — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\u2600\ufe0f Votre résumé quotidien</h2>'
     '<p style="margin:0 0 16px">Bonjour {{ destinataire.prenom }}, voici les dernières actualités de votre résidence.</p>'
     '<hr style="border:none;border-top:1px solid #D0D8E4;margin:0 0 16px">',
     True),

    ("digest_hebdomadaire", "Digest hebdomadaire", "Résumé de la semaine — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">\U0001f4ca Résumé de la semaine</h2>'
     '<p style="margin:0 0 16px">Bonjour {{ destinataire.prenom }}, voici un récapitulatif de la semaine écoulée sur votre résidence.</p>'
     '<hr style="border:none;border-top:1px solid #D0D8E4;margin:0 0 16px">',
     True),

    ("sauvegarde_echec", "Échec sauvegarde", "ALERTE — Échec de la sauvegarde automatique",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#c0392b">\u26a0 Échec de la sauvegarde</h2>'
     '<p style="margin:0 0 12px">La sauvegarde automatique du <strong>{{ date }}</strong> a échoué.</p>'
     '<table role="presentation" style="width:100%;margin:0 0 12px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
     '<p style="margin:0;font-family:monospace;font-size:13px;color:#1A1A2E">{{ erreur }}</p>'
     '</td></tr></table>'
     '<p style="margin:0;color:#5A6070;font-size:13px">Veuillez vérifier la configuration des sauvegardes dans l\u2019administration.</p>',
     False),

    ("alerte_espace_disque", "Alerte espace disque", "ALERTE — Espace disque faible ({{ pourcentage_libre }}% libre)",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#c0392b">\u26a0 Espace disque faible</h2>'
     '<p style="margin:0 0 12px">Le serveur ne dispose plus que de <strong>{{ pourcentage_libre }}%</strong> d\u2019espace disque libre.</p>'
     '<table role="presentation" style="width:100%;margin:0 0 12px;border:1px solid #D0D8E4;border-radius:8px;overflow:hidden"><tr>'
     '<td style="background:#FDF0F0;padding:16px;border-left:4px solid #c0392b">'
     '<p style="margin:0 0 4px;font-size:14px;color:#1A1A2E"><strong>Espace disponible :</strong> {{ espace_disponible }} sur {{ espace_total }}</p>'
     '</td></tr></table>'
     '<p style="margin:0;color:#5A6070;font-size:13px">Veuillez libérer de l\u2019espace sur le serveur (images Docker, backups, logs\u2026) ou étendre le stockage.</p>',
     False),

    ("verification_email", "Vérification e-mail", "Vérifiez votre adresse e-mail — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Vérification de votre adresse e-mail</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ prenom }},</p>'
     '<p style="margin:0 0 24px">Cliquez sur le bouton ci-dessous pour confirmer votre adresse e-mail.</p>'
     '<p style="text-align:center;margin:0 0 16px"><a href="{{ lien }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Vérifier mon adresse</a></p>'
     '<p style="margin:0;font-size:13px;color:#5A6070">Ce lien est valable <strong>{{ expire_heures }} heures</strong>. Si vous n\u2019êtes pas à l\u2019origine de cette demande, ignorez ce message.</p>',
     False),
]


def seed():
    create_db_and_tables()

    with Session(engine) as session:
        # Copropriété par défaut
        if not session.exec(select(Copropriete)).first():
            copro = Copropriete(
                nom="Ma Résidence",
                adresse="1 rue Exemple, 75000 Paris",
                annee_construction=2000,
                nb_lots_total=48,
            )
            session.add(copro)
            session.flush()

            for letter in ["1", "2", "3", "4"]:
                session.add(Batiment(copropriete_id=copro.id, numero=letter, nb_etages=5))

        # Admin par défaut — mot de passe aléatoire affiché dans les logs au 1er lancement
        if not session.exec(select(Utilisateur).where(Utilisateur.role == RoleUtilisateur.admin)).first():
            import secrets
            temp_pwd = secrets.token_urlsafe(16)
            admin = Utilisateur(
                nom="Admin",
                prenom="Site",
                email="admin@localhost",
                hashed_password=hash_password(temp_pwd),
                statut=StatutUtilisateur.admin_technique,
                role=RoleUtilisateur.admin,
                roles_json="admin",
                actif=True,
                consentement_rgpd=True,
            )
            session.add(admin)
            import logging
            logging.getLogger("app.seed").warning(
                "\n" + "=" * 60
                + "\n  ADMIN INITIAL CRÉÉ"
                + "\n  Email : admin@localhost"
                + f"\n  Mot de passe temporaire : {temp_pwd}"
                + "\n  ⚠ Changez-le immédiatement après la 1ʳᵉ connexion."
                + "\n" + "=" * 60
            )

        # Profils d'accès documentaires
        profil_map: dict[str, int] = {}
        for p in PROFILS:
            existing = session.exec(
                select(ProfilAccesDocument).where(ProfilAccesDocument.code == p["code"])
            ).first()
            if not existing:
                obj = ProfilAccesDocument(**p)
                session.add(obj)
                session.flush()
                profil_map[obj.code] = obj.id
            else:
                profil_map[existing.code] = existing.id

        # Catégories de documents
        for code, libelle, profil_code, perimetre, surcharge in CATEGORIES:
            if not session.exec(select(CategorieDocument).where(CategorieDocument.code == code)).first():
                session.add(CategorieDocument(
                    code=code,
                    libelle=libelle,
                    profil_acces_id=profil_map[profil_code],
                    perimetre_defaut=perimetre,
                    surcharge_autorisee=surcharge,
                ))

        # Configuration sauvegarde par défaut
        if not session.exec(select(ConfigSauvegarde)).first():
            session.add(ConfigSauvegarde())

        # Configuration site par défaut
        DEFAULT_CONFIG = {
            'site_nom': 'Ma Résidence',
            'site_url': 'https://example.com/',
            'site_email': 'admin@example.com',
            'site_manager_user_id': '',
            'login_sous_titre': 'Votre espace numérique de résidence',
            'notify_ticket_bug_email': '0',
            'notify_new_user_created_email': '0',
            'whatsapp_footer': '— Le Conseil Syndical',
            'email_footer': '— ©2026-5Hostachy - Envoyé depuis 5hostachy.fr —',
            'reference_copro': '',
            **DEFAULT_LEGAL,
        }
        for cle, valeur in DEFAULT_CONFIG.items():
            if not session.get(ConfigSite, cle):
                session.add(ConfigSite(cle=cle, valeur=valeur))

        # Templates email
        for code, libelle, sujet, corps_html, desactivable in EMAIL_TEMPLATES:
            if not session.exec(select(ModeleEmail).where(ModeleEmail.code == code)).first():
                session.add(ModeleEmail(
                    code=code,
                    libelle=libelle,
                    sujet=sujet,
                    corps_html=corps_html,
                    desactivable=desactivable,
                ))

        session.commit()

        # FAQ items par défaut
        if not session.exec(select(FaqItem)).first():
            faq_items = [
                ("\U0001f5d1\ufe0f Tri des déchets", "Quels déchets vont dans le bac jaune ?", "Le bac jaune est réservé aux emballages recyclables : cartons, plastiques rigides (bouteilles, flacons), briques alimentaires, canettes. Ne pas y mettre le verre ni les sacs plastiques.", 1),
                ("\U0001f5d1\ufe0f Tri des déchets", "Où sont les conteneurs à verre ?", "Les conteneurs à verre (vert) sont situés à l'entrée du parking, côté est. Merci de ne pas y déposer de vaisselle, vitres ou miroirs.", 2),
                ("\U0001f5d1\ufe0f Tri des déchets", "Comment me débarrasser d'encombrants ?", "Pour les encombrants (meubles, appareils), il faut contacter la mairie ou solliciter une collecte spéciale. Ne pas laisser d'objets dans les parties communes.", 3),
                ("\U0001f697 Stationnement", "Est-ce que je peux prêter ma place à un tiers ?", "Oui, un propriétaire peut mettre sa place à disposition d'un autre résident ou d'un tiers, mais il reste responsable de son usage. Toute location commerciale doit être signalée au syndic.", 4),
                ("\U0001f697 Stationnement", "Un véhicule stationne illégalement dans ma place, que faire ?", "Signalez-le d'abord au conseil syndical via cette application (Tickets). En cas d'urgence, vous pouvez contacter directement la fourrière municipale.", 5),
                ("\U0001f697 Stationnement", "Y a-t-il des bornes de recharge électrique ?", "Une étude de faisabilité est en cours pour l'installation de bornes IRVE. Consultez la rubrique Gouvernance pour suivre l'avancement du projet.", 6),
                ("\U0001f528 Travaux", "Quels travaux nécessitent une autorisation de l'assemblée générale ?", "Tout travail sur les parties communes (façade, toiture) doit être voté en AG. Les travaux dans les parties privatives restent libres mais ne doivent pas modifier l'aspect extérieur.", 7),
                ("\U0001f528 Travaux", "Quelles sont les plages horaires autorisées pour les travaux ?", "Les travaux bruyants sont autorisés du lundi au vendredi de 8h à 12h et de 14h à 19h, le samedi de 9h à 12h et de 15h à 18h. Pas de travaux le dimanche.", 8),
                ("\U0001f4de Contacts d'urgence", "Qui contacter en cas de fuite d'eau ?", "En priorité, coupez l'eau au robinet d'arrêt de votre lot. Pour une fuite en parties communes, appelez immédiatement le syndic ou le gardien.", 9),
                ("\U0001f4de Contacts d'urgence", "Numéros d'urgence importants", "SAMU : 15 | Pompiers : 18 | Police secours : 17 | Urgence européen : 112 | Urgences EDF/ENEDIS : 09 72 67 50 00", 10),
                ("\U0001f4f1 Application 5Hostachy", "Comment changer mon mot de passe ?", "Rendez-vous dans Mon profil > Sécurité, puis cliquez sur Changer mon mot de passe.", 11),
                ("\U0001f4f1 Application 5Hostachy", "L'application fonctionne-t-elle hors connexion ?", "5Hostachy est une application compatible PC, tablette et mobile nécessitant une connexion internet. Elle peut s'installer sur l'écran d'accueil de votre téléphone comme une vraie app, mais les fonctions principales (tickets, messagerie, documents) restent inaccessibles sans réseau.", 12),
            ]
            for cat, question, reponse, ordre in faq_items:
                session.add(FaqItem(categorie=cat, question=question, reponse=reponse, ordre=ordre, actif=True))

        extra_faq_items = [
            ("\U0001f4f1 Application 5Hostachy", "Pourquoi mes anciens tickets n'apparaissent plus dans la liste principale ?", "Les tickets résolus, annulés ou fermés depuis plus de 48 h sont automatiquement déplacés dans la section <strong>Historique de mes tickets</strong>, en bas de la page Tickets. Cela permet de garder la liste principale centrée sur les demandes encore actives ou récentes.", 13),
            ("\U0001f4f1 Application 5Hostachy", "Que voit le conseil syndical lorsqu'il traite mon ticket ?", "Dans l'<strong>Espace CS</strong>, le conseil syndical voit le détail du ticket, son historique, ainsi que le <strong>prénom / nom</strong> et le <strong>bâtiment</strong> du demandeur afin d'identifier plus rapidement le contexte de la demande. Le CS peut ensuite changer le statut et ajouter un commentaire de suivi.", 14),
        ]
        existing_questions = set(session.exec(select(FaqItem.question)).all())
        for cat, question, reponse, ordre in extra_faq_items:
            if question not in existing_questions:
                session.add(FaqItem(categorie=cat, question=question, reponse=reponse, ordre=ordre, actif=True))

        session.commit()

        # Types de diagnostics réglementaires
        DIAGNOSTIC_TYPES = [
            {
                "code": "dpe",
                "nom": "DPE collectif",
                "texte_legislatif": "Loi Grenelle II (2010) — obligatoire pour les copropriétés de plus de 50 lots avec équipements collectifs de chauffage ou de refroidissement. Valable 10 ans sauf réalisation de travaux importants.",
                "frequence": "10 ans",
                "ordre": 1,
            },
            {
                "code": "amiante",
                "nom": "Diagnostic amiante (DAPP)",
                "texte_legislatif": "Loi du 02/08/1997 et Décret n°96-97 — obligatoire pour tout immeuble bâti avant le 01/07/1997. Permanent si aucune trace d'amiante détectée. Révision tous les 3 ans ou après travaux si présence constatée.",
                "frequence": "Permanent (révision si amiante détecté)",
                "ordre": 2,
            },
            {
                "code": "plomb",
                "nom": "Diagnostic plomb — CREP parties communes",
                "texte_legislatif": "Décret n°99-483 du 09/06/1999 — obligatoire pour les parties communes d'immeubles construits avant le 01/01/1949. Permanent si aucun revêtement contenant du plomb au-dessus du seuil. Révision obligatoire si dépassement du seuil.",
                "frequence": "Permanent (révision si plomb > seuil)",
                "ordre": 3,
            },
            {
                "code": "electricite",
                "nom": "Diagnostic électricité — parties communes",
                "texte_legislatif": "Décret n°2016-1092 du 08/08/2016 — contrôle des installations électriques des parties communes d'immeubles de plus de 15 ans. Réalisé par un diagnostiqueur certifié.",
                "frequence": "3 ans",
                "ordre": 4,
            },
            {
                "code": "gaz",
                "nom": "Diagnostic gaz — parties communes",
                "texte_legislatif": "Décret n°2016-1250 du 22/09/2016 — contrôle des installations de gaz collectif dans les parties communes. Obligatoire si chaudière collective ou réseau gaz de plus de 15 ans.",
                "frequence": "3 ans",
                "ordre": 5,
            },
            {
                "code": "ascenseur",
                "nom": "CTQ ascenseurs",
                "texte_legislatif": "Décret n°2004-964 du 09/09/2004 — contrôle technique quinquennal obligatoire pour tout ascenseur, réalisé par un organisme agréé indépendant de l'entreprise de maintenance. À compléter par une vérification annuelle.",
                "frequence": "5 ans",
                "ordre": 6,
            },
            {
                "code": "pppt",
                "nom": "Plan Pluriannuel de Travaux (PPPT)",
                "texte_legislatif": "Loi Climat et Résilience du 22/08/2021 (art. 90) — obligatoire pour les copropriétés de plus de 15 ans. Réalisé par un professionnel qualifié, soumis au vote de l'AG et renouvelé tous les 10 ans.",
                "frequence": "10 ans",
                "ordre": 7,
            },
            {
                "code": "audit_energetique",
                "nom": "Audit énergétique global",
                "texte_legislatif": "Loi Énergie-Climat du 08/11/2019 — obligatoire préalablement à la réalisation du PPPT pour les copropriétés classées D, E, F ou G au DPE collectif. Permet d'identifier les travaux prioritaires de rénovation.",
                "frequence": "Selon DPE (avant PPPT)",
                "ordre": 8,
            },
            {
                "code": "erp",
                "nom": "État des Risques et Pollutions (ERP)",
                "texte_legislatif": "Loi Alur (2014) et Art. R125-26 CCH — obligatoire lors de toute vente ou mise en location d'un bien situé dans une zone à risques délimitée par arrêté préfectoral. Valable 6 mois. Document à annexer à toute promesse ou bail.",
                "frequence": "6 mois (lors de mutations)",
                "ordre": 9,
            },
            {
                "code": "termites",
                "nom": "Diagnostic termites",
                "texte_legislatif": "Code de la construction L271-6 — obligatoire dans les zones géographiques délimitées par arrêté préfectoral. Valable 6 mois pour les transactions immobilières. À renouveler à chaque vente ou bail dans les zones concernées.",
                "frequence": "6 mois (dans les zones à risque)",
                "ordre": 10,
            },
        ]
        for dt in DIAGNOSTIC_TYPES:
            if not session.exec(select(DiagnosticType).where(DiagnosticType.code == dt["code"])).first():
                session.add(DiagnosticType(**dt))

        session.commit()
        print("\u2705 Seed terminé.")


if __name__ == "__main__":
    seed()
