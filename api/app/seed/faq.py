"""Questions fréquentes livrées par défaut.

Deux listes, et la distinction compte : `FAQ_INITIALE` n'est posée que sur une
base encore vierge de toute FAQ — la réécrire n'aurait aucun effet sur une
installation en service, où le conseil syndical a pu tout retoucher.
`FAQ_COMPLEMENTAIRE` est ajoutée question par question, si la question n'existe
pas déjà : c'est la voie à suivre pour enrichir la FAQ après coup.

Format : (catégorie, question, réponse, ordre).
"""

FAQ_INITIALE = [
    (
        "🗑\ufe0f Tri des déchets",
        "Quels déchets vont dans le bac jaune ?",
        "Le bac jaune est réservé aux emballages recyclables : cartons, plastiques rigides (bouteilles, flacons), briques alimentaires, canettes. Ne pas y mettre le verre ni les sacs plastiques.",
        1,
    ),
    (
        "🗑\ufe0f Tri des déchets",
        "Où sont les conteneurs à verre ?",
        "Les conteneurs à verre (vert) sont situés à l'entrée du parking, côté est. Merci de ne pas y déposer de vaisselle, vitres ou miroirs.",
        2,
    ),
    (
        "🗑\ufe0f Tri des déchets",
        "Comment me débarrasser d'encombrants ?",
        "Pour les encombrants (meubles, appareils), il faut contacter la mairie ou solliciter une collecte spéciale. Ne pas laisser d'objets dans les parties communes.",
        3,
    ),
    (
        "🚗 Stationnement",
        "Est-ce que je peux prêter ma place à un tiers ?",
        "Oui, un propriétaire peut mettre sa place à disposition d'un autre résident ou d'un tiers, mais il reste responsable de son usage. Toute location commerciale doit être signalée au syndic.",
        4,
    ),
    (
        "🚗 Stationnement",
        "Un véhicule stationne illégalement dans ma place, que faire ?",
        "Signalez-le d'abord au conseil syndical via cette application (Affaires). En cas d'urgence, vous pouvez contacter directement la fourrière municipale.",
        5,
    ),
    (
        "🚗 Stationnement",
        "Y a-t-il des bornes de recharge électrique ?",
        "Une étude de faisabilité est en cours pour l'installation de bornes IRVE. Consultez la rubrique Résidence pour suivre l'avancement du projet.",
        6,
    ),
    (
        "🔨 Travaux",
        "Quels travaux nécessitent une autorisation de l'assemblée générale ?",
        "Tout travail sur les parties communes (façade, toiture) doit être voté en AG. Les travaux dans les parties privatives restent libres mais ne doivent pas modifier l'aspect extérieur.",
        7,
    ),
    (
        "🔨 Travaux",
        "Quelles sont les plages horaires autorisées pour les travaux ?",
        "Les travaux bruyants sont autorisés du lundi au vendredi de 8h à 12h et de 14h à 19h, le samedi de 9h à 12h et de 15h à 18h. Pas de travaux le dimanche.",
        8,
    ),
    (
        "📞 Contacts d'urgence",
        "Qui contacter en cas de fuite d'eau ?",
        "En priorité, coupez l'eau au robinet d'arrêt de votre lot. Pour une fuite en parties communes, appelez immédiatement le syndic ou le gardien.",
        9,
    ),
    (
        "📞 Contacts d'urgence",
        "Numéros d'urgence importants",
        "SAMU : 15 | Pompiers : 18 | Police secours : 17 | Urgence européen : 112 | Urgences EDF/ENEDIS : 09 72 67 50 00",
        10,
    ),
    (
        "📱 Application 5Hostachy",
        "Comment changer mon mot de passe ?",
        "Rendez-vous dans Mon profil, section Modifier le mot de passe, et saisissez votre mot de passe actuel puis le nouveau.",
        11,
    ),
    (
        "📱 Application 5Hostachy",
        "L'application fonctionne-t-elle hors connexion ?",
        "5Hostachy est une application compatible PC, tablette et mobile nécessitant une connexion internet. Elle peut s'installer sur l'écran d'accueil de votre téléphone comme une vraie app, mais les fonctions principales (affaires, documents, accès) restent inaccessibles sans réseau.",
        12,
    ),
]

FAQ_COMPLEMENTAIRE = [
    (
        "📱 Application 5Hostachy",
        "Pourquoi mes anciennes affaires n'apparaissent plus dans la liste principale ?",
        "Les affaires résolues ou annulées passent automatiquement dans l'onglet <strong>🗂️ Archives</strong> de la page Affaires, après un délai fixé par le conseil syndical. Cela garde la liste principale centrée sur les demandes encore actives, sans rien perdre : tout reste consultable dans les archives.",
        13,
    ),
    (
        "📱 Application 5Hostachy",
        "Que voit le conseil syndical lorsqu'il traite mon affaire ?",
        "Le conseil syndical traite les demandes depuis la page <strong>Affaires</strong>, où il voit le détail, l'historique, ainsi que le <strong>prénom / nom</strong> et le <strong>bâtiment</strong> du demandeur, afin de situer rapidement le contexte. Il peut y changer le statut et ajouter un commentaire de suivi. L'<strong>Espace CS</strong>, lui, en donne la vue d'ensemble dans son onglet Reporting.",
        14,
    ),
    #  🔴 Cette question est APPELÉE par deux descriptifs d'écran (`pages.ts`,
    #  onglets Badges et Télécommandes de « Mes lots & accès ») via le lien
    #  `/faq#badge-prix`, et le manuel la documente — mais **aucune question du
    #  seed ne contenait « prix »** jusqu'au 19/09/2026 (#1037). Le lien
    #  n'aboutissait donc que si le conseil syndical avait créé la question à la
    #  main : deux écrans renvoyaient vers une ancre morte.
    #
    #  Le résolveur (`faq/+page.svelte:198`) cherche par LIBELLÉ, pas par
    #  identifiant — celui-ci varie d'une instance à l'autre. Le libellé doit
    #  donc satisfaire `/quel\s+prix.*badge|prix.*badge|badge.*prix/i`.
    #
    #  ⚠️ La réponse ne cite **aucun montant** : le tarif est propre à chaque
    #  copropriété et se vote. Y écrire un chiffre serait inventer une donnée de
    #  référence, et elle serait fausse partout ailleurs (`standards/06`).
    (
        "📱 Application 5Hostachy",
        "Quel prix pour un badge ou une télécommande ?",
        "Le tarif d'un badge Vigik ou d'une télécommande de parking est fixé par la copropriété, et non par l'application : il couvre le coût du support et sa programmation. Le montant en vigueur est indiqué par le conseil syndical ou le syndic, et figure dans les décisions d'assemblée générale. Depuis <strong>Mes lots &amp; accès</strong>, la demande d'un accès supplémentaire se fait avec le bouton « + Nouvel accès » ; déclarer un accès que vous détenez déjà est gratuit.",
        16,
    ),
    (
        "📱 Application 5Hostachy",
        "Pourquoi mon nom apparaît-il sur une demande que je n'ai pas saisie ?",
        "Le conseil syndical peut enregistrer une demande <strong>pour</strong> quelqu'un — ce que vous avez signalé par téléphone, par exemple. Le formulaire porte alors une section <strong>Saisi pour</strong>, et c'est votre nom qui s'affiche sur la fiche : c'est bien de votre demande qu'il s'agit, et vous recevez les courriels de suivi. La personne qui a fait la saisie reste indiquée comme auteur — les deux informations coexistent parce qu'elles ne disent pas la même chose. Cela vaut pour les affaires comme pour les actualités.",
        15,
    ),
]
