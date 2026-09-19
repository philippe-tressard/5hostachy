"""La FAQ semée citait quatre écrans renommés ou supprimés (19/09/2026, #1037).

## Ce que le texte servi affirme, et ce que le produit fait

| Texte semé | Ce qui est vrai aujourd'hui |
|---|---|
| « Consultez la rubrique **Gouvernance** » | `gouvernance/+page.svelte` **redirige** vers `/residence` et ne figure plus dans `pages.ts` |
| « section **Historique de mes tickets** » | renommée « 🗂️ Archives » le 20/08/2026 (#516) |
| « depuis plus de **7 jours** » | `ARCHIVAGE_DELAI_JOURS = 30`, et **réglable** : un chiffre dans la FAQ redevient faux au premier réglage |
| « Dans l'**Espace CS**, le conseil syndical voit le détail du ticket… change le statut » | les tickets se traitent depuis la page **Tickets** ; l'Espace CS n'en donne qu'une vue d'ensemble dans Reporting |
| « tickets, **messagerie**, documents » | il n'y a **aucune** messagerie dans le produit |
| « Mon profil > **Sécurité** » | le bloc s'appelle « Modifier le mot de passe » (#1025) |

Un résident qui suit ces textes cherche un écran qui n'existe pas. C'est le
défaut le plus coûteux d'une FAQ : elle est lue **au moment où l'on ne sait pas**,
donc par quelqu'un qui n'a aucun moyen de corriger ce qu'il lit.

## 🔴 Pourquoi une migration, et pas seulement le seed

`FAQ_INITIALE` n'est posée que sur une base **vierge** : corriger le seed ne
change rien à une installation en service (`standards/06` §4). C'est exactement
la situation de la 0195, et le même remède s'applique.

⚠️ Chaque remplacement est **conditionnel** : il ne s'applique que si le texte
est encore celui qui a été semé, comparé au caractère près. Un conseil syndical
qui aurait déjà reformulé une réponse garde la sienne — **une migration de
données n'écrase pas un travail humain qu'elle ne sait pas relire.**

Et rien n'est **ajouté** ici : la nouvelle question « Quel prix pour un badge ou
une télécommande ? » passe par `FAQ_COMPLEMENTAIRE`, qui l'ajoute si elle
manque, au démarrage. C'est la voie prévue pour enrichir une FAQ en service, et
elle respecte ce que le conseil syndical a pu écrire de son côté.

Revision ID: 0198
Revises: 0197
Create Date: 2026-09-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0198"
down_revision = "0197"
branch_labels = None
depends_on = None

#: (question, ancienne réponse semée, nouvelle réponse). La question sert de
#: clé ; l'ancienne réponse sert de **garde** : elle distingue « personne n'y a
#: touché » de « quelqu'un l'a réécrit ».
REPONSES_A_CORRIGER = [
    (
        "Y a-t-il des bornes de recharge électrique ?",
        "Une étude de faisabilité est en cours pour l'installation de bornes IRVE. "
        "Consultez la rubrique Gouvernance pour suivre l'avancement du projet.",
        "Une étude de faisabilité est en cours pour l'installation de bornes IRVE. "
        "Consultez la rubrique Résidence pour suivre l'avancement du projet.",
    ),
    (
        "Comment changer mon mot de passe ?",
        "Rendez-vous dans Mon profil > Sécurité, puis cliquez sur Changer mon mot de passe.",
        "Rendez-vous dans Mon profil, section Modifier le mot de passe, et saisissez "
        "votre mot de passe actuel puis le nouveau.",
    ),
    (
        "L'application fonctionne-t-elle hors connexion ?",
        "5Hostachy est une application compatible PC, tablette et mobile nécessitant "
        "une connexion internet. Elle peut s'installer sur l'écran d'accueil de votre "
        "téléphone comme une vraie app, mais les fonctions principales (tickets, "
        "messagerie, documents) restent inaccessibles sans réseau.",
        "5Hostachy est une application compatible PC, tablette et mobile nécessitant "
        "une connexion internet. Elle peut s'installer sur l'écran d'accueil de votre "
        "téléphone comme une vraie app, mais les fonctions principales (tickets, "
        "documents, calendrier) restent inaccessibles sans réseau.",
    ),
    (
        "Pourquoi mes anciens tickets n'apparaissent plus dans la liste principale ?",
        "Les tickets résolus ou annulés depuis plus de 7 jours sont automatiquement "
        "déplacés dans la section <strong>Historique de mes tickets</strong>, en bas de "
        "la page Tickets. Cela permet de garder la liste principale centrée sur les "
        "demandes encore actives ou récentes.",
        "Les tickets résolus ou annulés passent automatiquement dans l'onglet "
        "<strong>🗂️ Archives</strong> de la page Tickets, après un délai fixé par le "
        "conseil syndical. Cela garde la liste principale centrée sur les demandes "
        "encore actives, sans rien perdre : tout reste consultable dans les archives.",
    ),
    (
        "Que voit le conseil syndical lorsqu'il traite mon ticket ?",
        "Dans l'<strong>Espace CS</strong>, le conseil syndical voit le détail du "
        "ticket, son historique, ainsi que le <strong>prénom / nom</strong> et le "
        "<strong>bâtiment</strong> du demandeur afin d'identifier plus rapidement le "
        "contexte de la demande. Le CS peut ensuite changer le statut et ajouter un "
        "commentaire de suivi.",
        "Le conseil syndical traite les demandes depuis la page <strong>Tickets</strong>, "
        "où il voit le détail, l'historique, ainsi que le <strong>prénom / nom</strong> "
        "et le <strong>bâtiment</strong> du demandeur, afin de situer rapidement le "
        "contexte. Il peut y changer le statut et ajouter un commentaire de suivi. "
        "L'<strong>Espace CS</strong>, lui, en donne la vue d'ensemble dans son onglet "
        "Reporting.",
    ),
]


def _remplacer(conn, question: str, avant: str, apres: str) -> int:
    resultat = conn.execute(
        sa.text(
            "UPDATE faq_item SET reponse = :apres, mis_a_jour_le = CURRENT_TIMESTAMP "
            "WHERE question = :question AND reponse = :avant"
        ).bindparams(question=question, avant=avant, apres=apres)
    )
    return resultat.rowcount or 0


def upgrade() -> None:
    conn = op.get_bind()
    for question, avant, apres in REPONSES_A_CORRIGER:
        _remplacer(conn, question, avant, apres)


def downgrade() -> None:
    #  Symétrique, et sous la même garde : on ne remet l'ancien texte que si le
    #  nouveau est intact. Un retour en arrière ne défait pas une reformulation
    #  faite entre-temps.
    conn = op.get_bind()
    for question, avant, apres in REPONSES_A_CORRIGER:
        _remplacer(conn, question, apres, avant)
