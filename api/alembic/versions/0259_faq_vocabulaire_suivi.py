"""La FAQ dit « ajouter une suite » et « section Au nom de » (#1594).

Deux réponses de la FAQ nommaient ce que l'écran ne dit pas :

| Texte semé | Ce que l'écran dit |
|---|---|
| « ajouter un commentaire de suivi » | la section « Suivi », le geste « Ajouter une suite » |
| « une section <strong>Saisi pour</strong> » | la section s'appelle « Au nom de » (`$lib/entites/types.ts`) ; « Saisi pour » est le champ |

Le seed a été corrigé en v2.93.3, mais `FAQ_COMPLEMENTAIRE` n'ajoute qu'une
question absente : une installation en service garde l'ancien texte. Comme la
0217, chaque remplacement est gardé par le texte d'avant : une réponse
reformulée par le conseil syndical ou l'administrateur n'est pas touchée.

Revision ID: 0259
Revises: 0258
"""

from alembic import op

from app.utils.textes_livres import remplacer_si_intact

revision = "0259"
down_revision = "0258"
branch_labels = None
depends_on = None

#: (question, réponse avant, réponse après) — extraites du diff réel de
#: `app/seed/faq.py` (v2.93.3), jamais retapées : un texte approximatif ne
#: mettrait rien à jour, sans le dire.
ENTREES = [
    (
        "Que voit le conseil syndical lorsqu'il traite mon affaire ?",
        "Le conseil syndical traite les demandes depuis la page <strong>Affaires</strong>, où il voit le détail, l'historique, ainsi que le <strong>prénom / nom</strong> et le <strong>bâtiment</strong> du demandeur, afin de situer rapidement le contexte. Il peut y changer le statut et ajouter un commentaire de suivi. L'<strong>Espace CS</strong>, lui, en donne la vue d'ensemble dans son onglet Reporting.",
        "Le conseil syndical traite les demandes depuis la page <strong>Affaires</strong>, où il voit le détail, l'historique, ainsi que le <strong>prénom / nom</strong> et le <strong>bâtiment</strong> du demandeur, afin de situer rapidement le contexte. Il peut y changer le statut et y ajouter une suite. L'<strong>Espace CS</strong>, lui, en donne la vue d'ensemble dans son onglet Reporting.",
    ),
    (
        "Pourquoi mon nom apparaît-il sur une demande que je n'ai pas saisie ?",
        "Le conseil syndical peut enregistrer une demande <strong>pour</strong> quelqu'un — ce que vous avez signalé par téléphone, par exemple. Le formulaire porte alors une section <strong>Saisi pour</strong>, et c'est votre nom qui s'affiche sur la fiche : c'est bien de votre demande qu'il s'agit, et vous recevez les courriels de suivi. La personne qui a fait la saisie reste indiquée comme auteur — les deux informations coexistent parce qu'elles ne disent pas la même chose. Cela vaut pour les affaires comme pour les actualités.",
        "Le conseil syndical peut enregistrer une demande <strong>pour</strong> quelqu'un — ce que vous avez signalé par téléphone, par exemple. Le formulaire porte alors une section <strong>Au nom de</strong>, et c'est votre nom qui s'affiche sur la fiche : c'est bien de votre demande qu'il s'agit, et vous recevez les courriels de suivi. La personne qui a fait la saisie reste indiquée comme auteur — les deux informations coexistent parce qu'elles ne disent pas la même chose. Cela vaut pour les affaires comme pour les actualités.",
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for question, avant, apres in ENTREES:
        remplacer_si_intact(conn, "faq_item", {"question": question, "reponse": avant}, {"reponse": apres})


def downgrade() -> None:
    conn = op.get_bind()
    for question, avant, apres in ENTREES:
        remplacer_si_intact(conn, "faq_item", {"question": question, "reponse": apres}, {"reponse": avant})
