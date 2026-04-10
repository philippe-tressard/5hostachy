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
    ("invitation_resident", "Invitation résident", "Bienvenue sur {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }},</p><p>Vous avez été invité à rejoindre <strong>{{ residence.nom }}</strong>.</p><p><a href=\"{{ lien }}\">Créer mon compte</a></p>", False),
    ("reinitialisation_mdp", "Réinitialisation mot de passe", "Réinitialisation de votre mot de passe — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }},</p><p><a href=\"{{ lien }}\">Réinitialiser mon mot de passe</a> (valable 1 heure)</p>", False),
    ("compte_en_attente", "Compte en attente", "Nouvelle demande de compte — {{ residence.nom }}", "<p>Un nouveau compte est en attente de validation : {{ utilisateur.prenom }} {{ utilisateur.nom }} ({{ utilisateur.email }}).</p>", True),
    ("compte_active", "Compte activé", "Votre compte est activé — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, votre compte est maintenant actif. <a href=\"{{ app.url }}\">Accéder à l'application</a></p>", True),
    ("compte_refuse", "Compte refusé", "Votre demande de compte — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, votre demande n'a pas pu être acceptée. Contactez le conseil syndical.</p>", True),
    ("locataire_validation_demande", "Demande validation locataire", "Un locataire souhaite s'inscrire sur votre lot — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, {{ locataire.prenom }} {{ locataire.nom }} souhaite s'inscrire en tant que locataire de votre lot {{ lot.numero }}.</p>", True),
    ("locataire_valide", "Locataire validé", "Votre inscription a été validée — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, votre inscription en tant que locataire a été validée.</p>", True),
    ("locataire_refuse", "Locataire refusé", "Votre inscription n'a pas été acceptée — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, votre demande d'inscription n'a pas été acceptée.</p>", True),
    ("ticket_cree_cs", "Ticket créé (CS)", "Nouveau ticket #{{ ticket.numero }} — {{ residence.nom }}", "<p>Un nouveau ticket a été soumis par {{ auteur.prenom }} {{ auteur.nom }} : <strong>{{ ticket.titre }}</strong></p><p><a href=\"{{ app.url }}/tickets/{{ ticket.id }}\">Voir le ticket</a></p>", True),
    ("ticket_bug_admin", "Ticket bug — notification admin site", "Bug signalé via Tickets — {{ residence.nom }}", "<p>Un ticket de type <strong>Bug</strong> a été soumis par {{ auteur.prenom }} {{ auteur.nom }}{% if auteur.email %} ({{ auteur.email }}){% endif %}.</p><p><strong>{{ ticket.titre }}</strong></p><p>{{ ticket.description }}</p><p><a href=\"{{ app.url }}/tickets/{{ ticket.id }}\">Voir le ticket</a></p>", True),
    ("ticket_statut_change", "Statut ticket modifié", "Ticket #{{ ticket.numero }} mis à jour — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, le statut de votre ticket <strong>{{ ticket.titre }}</strong> est maintenant : {{ ticket.statut }}.</p>", True),
    ("ticket_urgence_bailleur", "Ticket urgence (bailleur)", "URGENT — Ticket sur votre lot {{ lot.numero }}", "<p>Bonjour {{ destinataire.prenom }}, un ticket <strong>URGENT</strong> a été soumis sur votre lot {{ lot.numero }} : {{ ticket.titre }}.</p>", True),
    ("vigik_commande_recue", "Commande vigik reçue (CS)", "Nouvelle commande de {{ type }} — {{ residence.nom }}", "<p>{{ demandeur.prenom }} {{ demandeur.nom }} a soumis une demande de {{ type }} pour le lot {{ lot.numero }}.</p>", True),
    ("vigik_accepte", "Commande vigik acceptée", "Votre demande de {{ type }} a été acceptée — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, votre demande a été acceptée.</p>", True),
    ("vigik_refuse", "Commande vigik refusée", "Votre demande de {{ type }} n'a pas été acceptée — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, votre demande a été refusée. Motif : {{ motif }}</p>", True),
    ("calendrier_evenement_cree", "Événement calendrier créé", "Nouvel événement : {{ evenement.titre }} — {{ residence.nom }}", "<p>Un événement a été ajouté au calendrier : <strong>{{ evenement.titre }}</strong> le {{ evenement.date }}.</p>", True),
    ("document_publie", "Document publié", "Nouveau document disponible — {{ residence.nom }}", "<p>Un nouveau document a été publié : <strong>{{ document.titre }}</strong>.</p>", True),
    ("digest_quotidien", "Digest quotidien", "Résumé du jour — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, voici votre résumé quotidien.</p>", True),
    ("digest_hebdomadaire", "Digest hebdomadaire", "Résumé de la semaine — {{ residence.nom }}", "<p>Bonjour {{ destinataire.prenom }}, voici votre résumé de la semaine.</p>", True),
    ("sauvegarde_echec", "Échec sauvegarde", "ALERTE — Échec de la sauvegarde automatique", "<p>La sauvegarde automatique du {{ date }} a échoué.</p><p>Erreur : {{ erreur }}</p>", False),
    ("verification_email", "Vérification e-mail", "Vérifiez votre adresse e-mail — {{ residence.nom }}", "<p>Bonjour {{ prenom }},</p><p>Cliquez sur le lien ci-dessous pour vérifier votre adresse e-mail (valable {{ expire_heures }} heures) :</p><p><a href=\"{{ lien }}\">Vérifier mon adresse e-mail</a></p>", False),
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
            'email_footer': '— Envoyé depuis 5hostachy.fr',
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
