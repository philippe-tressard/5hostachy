"""Modèles d'e-mail liés au compte et à son accès.

Ils partent hors de toute session ouverte — invitation, vérification, mot de passe oublié — et sont les seuls que reçoit quelqu'un qui n'est pas encore entré dans l'application. Un défaut ici empêche l'accès, il ne le dégrade pas.

Le gabarit commun (`email._wrap_email`) enveloppe ces contenus : pas de
`<html>` ni de `<body>` ici, seulement le corps riche.
"""

MODELES = [
    ("reinitialisation_mdp", "Réinitialisation mot de passe", "Réinitialisation de votre mot de passe — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Réinitialisation de votre mot de passe</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 24px">Une demande de réinitialisation a été effectuée pour votre compte. Cliquez sur le bouton ci-dessous pour choisir un nouveau mot de passe.</p>'
     '<p style="text-align:center;margin:0 0 16px"><a href="{{ lien }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Réinitialiser mon mot de passe</a></p>'
     '<p style="margin:0;font-size:13px;color:#5A6070">Ce lien est valable <strong>1 heure</strong>. Si vous n’avez pas fait cette demande, ignorez cet e-mail.</p>',
     False),
    ("verification_email", "Vérification e-mail", "Vérifiez votre adresse e-mail — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Vérification de votre adresse e-mail</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ prenom }},</p>'
     '<p style="margin:0 0 24px">Cliquez sur le bouton ci-dessous pour confirmer votre adresse e-mail.</p>'
     '<p style="text-align:center;margin:0 0 16px"><a href="{{ lien }}" style="display:inline-block;background:#C9983A;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Vérifier mon adresse</a></p>'
     '<p style="margin:0;font-size:13px;color:#5A6070">Ce lien est valable <strong>{{ expire_heures }} heures</strong>. Si vous n’êtes pas à l’origine de cette demande, ignorez ce message.</p>',
     False),
    ("compte_en_attente", "Compte en attente", "Nouvelle demande de compte — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Nouvelle demande de compte</h2>'
     '<p style="margin:0 0 12px">Un nouveau résident souhaite rejoindre la résidence\u202f:</p>'
     '<table role="presentation" style="margin:0 0 20px;border-left:4px solid #C9983A;padding-left:16px"><tr><td>'
     '<p style="margin:0 0 4px;font-weight:600;font-size:16px">{{ utilisateur.prenom }} {{ utilisateur.nom }}</p>'
     '<p style="margin:0;color:#5A6070">{{ utilisateur.email }}</p>'
     '</td></tr></table>'
     # `/admin/utilisateurs` n'existe pas : la page `/admin` s'ouvre d'elle-même
     # sur l'onglet « Comptes en attente », et ne lit pas `?onglet=`. Ce bouton
     # ouvrait un 404 depuis l'origine, dans un e-mail réellement envoyé.
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}/admin" style="display:inline-block;background:#1E3A5F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Valider le compte</a></p>',
     True),
    ("compte_active", "Compte activé", "Votre compte est activé — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Votre compte est activé\u202f!</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 24px">Votre compte sur <strong>{{ residence.nom }}</strong> est maintenant actif. Vous pouvez dès à présent accéder à l’ensemble des services de votre résidence.</p>'
     '<p style="text-align:center;margin:0"><a href="{{ app.url }}" style="display:inline-block;background:#3D6B4F;color:#ffffff;font-weight:600;font-size:15px;padding:12px 32px;border-radius:6px;text-decoration:none">Accéder à l’application</a></p>',
     True),
    ("compte_refuse", "Compte refusé", "Votre demande de compte — {{ residence.nom }}",
     '<h2 style="margin:0 0 16px;font-family:Georgia,serif;font-size:20px;color:#1E3A5F">Demande de compte non acceptée</h2>'
     '<p style="margin:0 0 12px">Bonjour {{ destinataire.prenom }},</p>'
     '<p style="margin:0 0 12px">Votre demande de création de compte sur <strong>{{ residence.nom }}</strong> n’a pas pu être acceptée.</p>'
     '<p style="margin:0;color:#5A6070">Si vous pensez qu’il s’agit d’une erreur, n’hésitez pas à contacter le conseil syndical.</p>',
     True),
]
