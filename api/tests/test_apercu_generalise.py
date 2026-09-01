"""Toute entité qui DIFFUSE doit pouvoir montrer ce qu'elle enverra (#498).

## 🔴 Pourquoi ce garde-fou existe

Le 19/08/2026 : *« avant la diffusion il faudrait voir le mail (aperçu) avant de
confirmer son envoi »*, puis *« cela est à intégrer partout où l'objet diffusion
par mail est concerné »*.

L'aperçu n'a été construit **que pour les tickets**. Le 31/08, une actualité est
partie au conseil syndical sans que son auteur ait rien pu voir ni annuler. Il
l'a signalé comme une régression ; ce n'en était pas une — c'était la moitié
jamais construite, et *la distinction ne change rien pour qui reçoit le mail*.

⚠️ Rien ne signalait le manque. Chaque écran savait envoyer ; aucun contrôle ne
demandait s'il savait **montrer**. Un écran ajouté demain repartirait sans, de la
même façon, et personne ne le verrait avant qu'un message soit parti.

## Ce que ce fichier vérifie

1. Chaque entité qui envoie un courriel de diffusion expose un endpoint
   d'aperçu ;
2. cet endpoint **délègue** aux assembleurs partagés — il ne recompose pas ;
3. l'envoi et l'aperçu prennent leur contexte à la **même** fonction.

Le point 3 est le plus important : un aperçu peut appeler la bonne fonction de
composition et rester faux si on lui donne un contexte fabriqué à la main.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[1] / "app"

#  Les entités qui diffusent par courriel, et où vivent leurs deux chemins.
#
#  ⚠️ Cette table est tenue à la main, et c'est assumé : le repérage automatique
#  d'« une entité qui diffuse » n'existe pas — c'est une notion métier. En
#  revanche le test échoue si l'un des fichiers cités disparaît, donc elle ne
#  peut pas pointer dans le vide sans se faire voir.
ENTITES = {
    "ticket": {
        "apercu": "routers/tickets/apercu.py",
        "envoi": "routers/tickets/courriels.py",
        "contexte": "contexte_ticket_syndic",
    },
    "publication": {
        "apercu": "routers/publications/apercu.py",
        "envoi": "routers/publications/courriels.py",
        "contexte": "contexte_publication_syndic",
    },
    "evenement": {
        "apercu": "routers/calendrier_apercu.py",
        "envoi": "routers/calendrier_courriels.py",
        "contexte": "contexte_evenement_canaux",
    },
    #  Dernière des quatre à recevoir l'aperçu (01/09/2026), et la seule qui en
    #  était privée DÉLIBÉRÉMENT : tant que son serveur ne consommait qu'un canal
    #  sur trois, un aperçu y aurait montré un envoi qui n'a pas lieu — le
    #  mensonge même que #498 existe pour empêcher. Les trois canaux sont
    #  consommés depuis #480, et la condition est levée.
    "annonce_hall": {
        "apercu": "routers/annonces_hall_apercu.py",
        "envoi": "routers/annonces_hall_courriels.py",
        "contexte": "contexte_annonce_hall",
    },
}

ASSEMBLEUR = _RACINE / "utils" / "apercu_diffusion.py"


def _source(rel: str) -> str:
    chemin = _RACINE / rel
    assert chemin.exists(), (
        f"{rel} est introuvable — ce test surveillait un fichier qui n'existe "
        "plus, il ne surveillait donc plus rien."
    )
    return chemin.read_text(encoding="utf-8")


def test_chaque_entite_qui_diffuse_a_son_apercu():
    """Un écran qui sait envoyer doit savoir montrer.

    C'est la règle que l'incident du 31/08/2026 a rendue nécessaire : personne
    n'avait remarqué que six entités sur sept en étaient dépourvues, parce que
    rien ne posait la question.
    """
    assert ASSEMBLEUR.exists(), (
        "L'assembleur partagé a disparu : les aperçus recomposent alors chacun "
        "de leur côté, et divergeront de l'envoi sans que rien ne le dise."
    )
    for entite, chemins in ENTITES.items():
        source = _source(chemins["apercu"])
        assert "apercu-diffusion" in source, (
            f"L'entité « {entite} » n'expose pas d'endpoint d'aperçu : on y coche "
            "un canal et l'on découvre le résultat en le recevant."
        )


def test_aucun_apercu_ne_recompose_de_son_cote():
    """Les routeurs délèguent aux assembleurs — sinon il y a de nouveau N rendus.

    🔴 Un aperçu qui ment est pire que pas d'aperçu (`standards/04` §14) : il
    deviendrait faux à la première évolution d'un gabarit, et personne ne s'en
    apercevrait, puisque c'est justement l'aperçu qu'on regarderait pour le
    vérifier.
    """
    for entite, chemins in ENTITES.items():
        source = _source(chemins["apercu"])
        assert "apercu_email(" in source or "apercu_whatsapp(" in source, (
            f"« {entite} » n'appelle aucun assembleur partagé."
        )
        for interdit in ("composer_email(", "construire_message(", "_contexte_rendu("):
            assert interdit not in source, (
                f"« {entite} » appelle `{interdit}` en direct : la composition doit "
                "rester dans `apercu_diffusion.py`, sinon il y en a de nouveau deux."
            )


def test_l_apercu_et_l_envoi_prennent_le_contexte_au_MEME_endroit():
    """Le point le plus fragile, et celui qu'aucune exécution ne révèle.

    Un aperçu peut employer la bonne fonction de composition et rester faux si on
    lui donne un contexte fabriqué à la main : les variables du gabarit
    divergeraient alors en silence. C'est la même famille que la clé `fichiers`
    absente d'un des deux envois pendant des mois.
    """
    for entite, chemins in ENTITES.items():
        nom = chemins["contexte"]
        apercu = _source(chemins["apercu"])
        envoi = _source(chemins["envoi"])
        assert f"{nom}(" in apercu, (
            f"L'aperçu de « {entite} » construit son propre contexte au lieu "
            f"d'appeler `{nom}` : ses variables peuvent diverger de l'envoi."
        )
        assert re.search(rf"^def {nom}\(", envoi, re.MULTILINE), (
            f"`{nom}` n'est pas défini dans {chemins['envoi']} : l'aperçu importe "
            "une fonction qui n'y est plus, et l'erreur ne se verrait qu'à "
            "l'exécution."
        )
        #  Et l'ENVOI l'appelle aussi : une fonction de contexte que seul
        #  l'aperçu emploierait ne prouve rien du tout.
        arbre = ast.parse(envoi)
        appels = {
            n.func.id
            for n in ast.walk(arbre)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert nom in appels, (
            f"L'envoi de « {entite} » n'appelle pas `{nom}` : la fonction existe, "
            "mais les deux chemins ne s'en servent pas — donc rien n'est partagé."
        )


def test_l_assembleur_appelle_les_fonctions_de_l_envoi():
    """Et lui-même ne réécrit rien : il passe par `composer_email` et le reste.

    C'est le maillon dont tout le reste dépend. S'il recomposait, les trois
    entités montreraient la même chose — et la même chose fausse.
    """
    source = ASSEMBLEUR.read_text(encoding="utf-8")
    for attendu in ("composer_email(", "_contexte_rendu(", "construire_message(",
                    "message_sans_contenu("):
        assert attendu in source, (
            f"L'assembleur n'appelle plus `{attendu}` : il compose de son côté, "
            "et les trois aperçus mentiront ensemble."
        )
