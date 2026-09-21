"""La FAQ dit « affaire », plus « ticket » (#1094).

Le chantier v2.0.0 renomme ce que l'utilisateur lit : « ticket » dit l'outil, pas
la chose. La FAQ vit **en base** — le seed ne pose que les instances neuves —,
d'où cette migration.

🔴 Ce qui ne bouge pas : la route `/tickets` (elle est dans des courriels déjà
envoyés), les identifiants `TK-xxxx`, et les noms de code. Seuls les mots lus par
un résident changent, et leurs **accords** avec : « ticket » est masculin,
« affaire » est féminin — « mes anciens tickets » devient « mes anciennes
affaires », pas « mes anciens affaires ».

⚠️ Chaque `UPDATE` est gardé par le texte d'avant (`WHERE question = … AND
reponse = …`) : une entrée reformulée en administration depuis le dernier
déploiement n'est pas écrasée. Le revers est que la migration est alors sans
effet sur cette entrée-là, en silence — c'est le compromis retenu par la
migration 0198, qui a posé ce motif.

⚠️ Les **modèles d'e-mail** portent encore le mot (57 occurrences dans
`seed/emails/tickets.py`). Ils ne sont pas dans ce lot : voir le ticket ouvert
pour eux, et la règle « ne pas élargir en route ».
"""
import sqlalchemy as sa
from alembic import op

revision = "0201"
down_revision = "0200"
branch_labels = None
depends_on = None

#: (question avant, réponse avant, question après, réponse après)
#: Extrait du diff réel de `app/seed/faq.py` — jamais retapé : un texte
#: approximatif ne mettrait rien à jour, sans le dire.
ENTREES = [
    (
        'Un véhicule stationne illégalement dans ma place, que faire ?',
        "Signalez-le d'abord au conseil syndical via cette application (Tickets). En cas d'urgence, vous pouvez contacter directement la fourrière municipale.",
        'Un véhicule stationne illégalement dans ma place, que faire ?',
        "Signalez-le d'abord au conseil syndical via cette application (Affaires). En cas d'urgence, vous pouvez contacter directement la fourrière municipale.",
    ),
    (
        "L'application fonctionne-t-elle hors connexion ?",
        "5Hostachy est une application compatible PC, tablette et mobile nécessitant une connexion internet. Elle peut s'installer sur l'écran d'accueil de votre téléphone comme une vraie app, mais les fonctions principales (tickets, documents, calendrier) restent inaccessibles sans réseau.",
        "L'application fonctionne-t-elle hors connexion ?",
        "5Hostachy est une application compatible PC, tablette et mobile nécessitant une connexion internet. Elle peut s'installer sur l'écran d'accueil de votre téléphone comme une vraie app, mais les fonctions principales (affaires, documents, calendrier) restent inaccessibles sans réseau.",
    ),
    (
        "Pourquoi mes anciens tickets n'apparaissent plus dans la liste principale ?",
        "Les tickets résolus ou annulés passent automatiquement dans l'onglet <strong>🗂️ Archives</strong> de la page Tickets, après un délai fixé par le conseil syndical. Cela garde la liste principale centrée sur les demandes encore actives, sans rien perdre : tout reste consultable dans les archives.",
        "Pourquoi mes anciennes affaires n'apparaissent plus dans la liste principale ?",
        "Les affaires résolues ou annulées passent automatiquement dans l'onglet <strong>🗂️ Archives</strong> de la page Affaires, après un délai fixé par le conseil syndical. Cela garde la liste principale centrée sur les demandes encore actives, sans rien perdre : tout reste consultable dans les archives.",
    ),
    (
        "Que voit le conseil syndical lorsqu'il traite mon ticket ?",
        "Le conseil syndical traite les demandes depuis la page <strong>Tickets</strong>, où il voit le détail, l'historique, ainsi que le <strong>prénom / nom</strong> et le <strong>bâtiment</strong> du demandeur, afin de situer rapidement le contexte. Il peut y changer le statut et ajouter un commentaire de suivi. L'<strong>Espace CS</strong>, lui, en donne la vue d'ensemble dans son onglet Reporting.",
        "Que voit le conseil syndical lorsqu'il traite mon affaire ?",
        "Le conseil syndical traite les demandes depuis la page <strong>Affaires</strong>, où il voit le détail, l'historique, ainsi que le <strong>prénom / nom</strong> et le <strong>bâtiment</strong> du demandeur, afin de situer rapidement le contexte. Il peut y changer le statut et ajouter un commentaire de suivi. L'<strong>Espace CS</strong>, lui, en donne la vue d'ensemble dans son onglet Reporting.",
    ),
    (
        "Pourquoi mon nom apparaît-il sur une demande que je n'ai pas saisie ?",
        "Le conseil syndical peut enregistrer une demande <strong>pour</strong> quelqu'un — ce que vous avez signalé par téléphone, par exemple. Le formulaire porte alors une section <strong>Saisi pour</strong>, et c'est votre nom qui s'affiche sur la fiche : c'est bien de votre demande qu'il s'agit, et vous recevez les courriels de suivi. La personne qui a fait la saisie reste indiquée comme auteur — les deux informations coexistent parce qu'elles ne disent pas la même chose. Cela vaut pour les tickets, les actualités et les événements.",
        "Pourquoi mon nom apparaît-il sur une demande que je n'ai pas saisie ?",
        "Le conseil syndical peut enregistrer une demande <strong>pour</strong> quelqu'un — ce que vous avez signalé par téléphone, par exemple. Le formulaire porte alors une section <strong>Saisi pour</strong>, et c'est votre nom qui s'affiche sur la fiche : c'est bien de votre demande qu'il s'agit, et vous recevez les courriels de suivi. La personne qui a fait la saisie reste indiquée comme auteur — les deux informations coexistent parce qu'elles ne disent pas la même chose. Cela vaut pour les affaires, les actualités et les événements.",
    ),
]


def _remplacer(conn, q_avant, r_avant, q_apres, r_apres) -> int:
    resultat = conn.execute(
        sa.text(
            "UPDATE faq_item SET question = :q_apres, reponse = :r_apres, "
            "mis_a_jour_le = CURRENT_TIMESTAMP "
            "WHERE question = :q_avant AND reponse = :r_avant"
        ).bindparams(q_avant=q_avant, r_avant=r_avant, q_apres=q_apres, r_apres=r_apres)
    )
    return resultat.rowcount or 0


def upgrade() -> None:
    conn = op.get_bind()
    for q_a, r_a, q_b, r_b in ENTREES:
        _remplacer(conn, q_a, r_a, q_b, r_b)


def downgrade() -> None:
    #  Symétrique, sous la même garde : on ne remet l'ancien texte que si le
    #  nouveau est intact — un retour en arrière ne défait pas une reformulation
    #  faite entre-temps.
    conn = op.get_bind()
    for q_a, r_a, q_b, r_b in ENTREES:
        _remplacer(conn, q_b, r_b, q_a, r_a)
