"""La FAQ ne parle plus du calendrier ni des événements (#1099).

Le calendrier est devenu un filtre d'Affaires et les événements des affaires
(#1092, 23/09/2026). Deux réponses de la FAQ les nommaient encore. Comme la
0201, chaque remplacement est gardé par le texte d'avant : une entrée
reformulée par le conseil syndical n'est pas touchée.

La garde vit désormais dans `utils/textes_livres.remplacer_si_intact`, et non
plus recopiée ici — elle l'était dans quinze migrations.
"""
from alembic import op

from app.utils.textes_livres import remplacer_si_intact

revision = "0217"
down_revision = "0216"
branch_labels = None
depends_on = None

#: (question, réponse avant, réponse après) — extraites du diff réel de
#: `app/seed/faq.py`, jamais retapées : un texte approximatif ne mettrait rien
#: à jour, sans le dire.
ENTREES = [
    (
        "L'application fonctionne-t-elle hors connexion ?",
        "5Hostachy est une application compatible PC, tablette et mobile nécessitant une connexion internet. Elle peut s'installer sur l'écran d'accueil de votre téléphone comme une vraie app, mais les fonctions principales (affaires, documents, calendrier) restent inaccessibles sans réseau.",
        "5Hostachy est une application compatible PC, tablette et mobile nécessitant une connexion internet. Elle peut s'installer sur l'écran d'accueil de votre téléphone comme une vraie app, mais les fonctions principales (affaires, documents, accès) restent inaccessibles sans réseau.",
    ),
    (
        "Pourquoi mon nom apparaît-il sur une demande que je n'ai pas saisie ?",
        "Le conseil syndical peut enregistrer une demande <strong>pour</strong> quelqu'un — ce que vous avez signalé par téléphone, par exemple. Le formulaire porte alors une section <strong>Saisi pour</strong>, et c'est votre nom qui s'affiche sur la fiche : c'est bien de votre demande qu'il s'agit, et vous recevez les courriels de suivi. La personne qui a fait la saisie reste indiquée comme auteur — les deux informations coexistent parce qu'elles ne disent pas la même chose. Cela vaut pour les affaires, les actualités et les événements.",
        "Le conseil syndical peut enregistrer une demande <strong>pour</strong> quelqu'un — ce que vous avez signalé par téléphone, par exemple. Le formulaire porte alors une section <strong>Saisi pour</strong>, et c'est votre nom qui s'affiche sur la fiche : c'est bien de votre demande qu'il s'agit, et vous recevez les courriels de suivi. La personne qui a fait la saisie reste indiquée comme auteur — les deux informations coexistent parce qu'elles ne disent pas la même chose. Cela vaut pour les affaires comme pour les actualités.",
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
