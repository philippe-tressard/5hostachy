"""Questions fréquentes livrées par défaut.

Deux listes, et la distinction compte : `FAQ_INITIALE` n'est posée que sur une
base encore vierge de toute FAQ — la réécrire n'aurait aucun effet sur une
installation en service, où le conseil syndical a pu tout retoucher.
`FAQ_COMPLEMENTAIRE` est ajoutée question par question, si la question n'existe
pas déjà : c'est la voie à suivre pour enrichir la FAQ après coup.

Format : (catégorie, question, réponse, ordre).
"""

FAQ_INITIALE = [
    ("🗑\ufe0f Tri des déchets", "Quels déchets vont dans le bac jaune ?", "Le bac jaune est réservé aux emballages recyclables : cartons, plastiques rigides (bouteilles, flacons), briques alimentaires, canettes. Ne pas y mettre le verre ni les sacs plastiques.", 1),
    ("🗑\ufe0f Tri des déchets", "Où sont les conteneurs à verre ?", "Les conteneurs à verre (vert) sont situés à l'entrée du parking, côté est. Merci de ne pas y déposer de vaisselle, vitres ou miroirs.", 2),
    ("🗑\ufe0f Tri des déchets", "Comment me débarrasser d'encombrants ?", "Pour les encombrants (meubles, appareils), il faut contacter la mairie ou solliciter une collecte spéciale. Ne pas laisser d'objets dans les parties communes.", 3),
    ("🚗 Stationnement", "Est-ce que je peux prêter ma place à un tiers ?", "Oui, un propriétaire peut mettre sa place à disposition d'un autre résident ou d'un tiers, mais il reste responsable de son usage. Toute location commerciale doit être signalée au syndic.", 4),
    ("🚗 Stationnement", "Un véhicule stationne illégalement dans ma place, que faire ?", "Signalez-le d'abord au conseil syndical via cette application (Tickets). En cas d'urgence, vous pouvez contacter directement la fourrière municipale.", 5),
    ("🚗 Stationnement", "Y a-t-il des bornes de recharge électrique ?", "Une étude de faisabilité est en cours pour l'installation de bornes IRVE. Consultez la rubrique Gouvernance pour suivre l'avancement du projet.", 6),
    ("🔨 Travaux", "Quels travaux nécessitent une autorisation de l'assemblée générale ?", "Tout travail sur les parties communes (façade, toiture) doit être voté en AG. Les travaux dans les parties privatives restent libres mais ne doivent pas modifier l'aspect extérieur.", 7),
    ("🔨 Travaux", "Quelles sont les plages horaires autorisées pour les travaux ?", "Les travaux bruyants sont autorisés du lundi au vendredi de 8h à 12h et de 14h à 19h, le samedi de 9h à 12h et de 15h à 18h. Pas de travaux le dimanche.", 8),
    ("📞 Contacts d'urgence", "Qui contacter en cas de fuite d'eau ?", "En priorité, coupez l'eau au robinet d'arrêt de votre lot. Pour une fuite en parties communes, appelez immédiatement le syndic ou le gardien.", 9),
    ("📞 Contacts d'urgence", "Numéros d'urgence importants", "SAMU : 15 | Pompiers : 18 | Police secours : 17 | Urgence européen : 112 | Urgences EDF/ENEDIS : 09 72 67 50 00", 10),
    ("📱 Application 5Hostachy", "Comment changer mon mot de passe ?", "Rendez-vous dans Mon profil > Sécurité, puis cliquez sur Changer mon mot de passe.", 11),
    ("📱 Application 5Hostachy", "L'application fonctionne-t-elle hors connexion ?", "5Hostachy est une application compatible PC, tablette et mobile nécessitant une connexion internet. Elle peut s'installer sur l'écran d'accueil de votre téléphone comme une vraie app, mais les fonctions principales (tickets, messagerie, documents) restent inaccessibles sans réseau.", 12),
]

FAQ_COMPLEMENTAIRE = [
    ("📱 Application 5Hostachy", "Pourquoi mes anciens tickets n'apparaissent plus dans la liste principale ?", "Les tickets résolus ou annulés depuis plus de 7 jours sont automatiquement déplacés dans la section <strong>Historique de mes tickets</strong>, en bas de la page Tickets. Cela permet de garder la liste principale centrée sur les demandes encore actives ou récentes.", 13),
    ("📱 Application 5Hostachy", "Que voit le conseil syndical lorsqu'il traite mon ticket ?", "Dans l'<strong>Espace CS</strong>, le conseil syndical voit le détail du ticket, son historique, ainsi que le <strong>prénom / nom</strong> et le <strong>bâtiment</strong> du demandeur afin d'identifier plus rapidement le contexte de la demande. Le CS peut ensuite changer le statut et ajouter un commentaire de suivi.", 14),
]
