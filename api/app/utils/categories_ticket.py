"""Le libellé français d'une catégorie de ticket — côté serveur.

## 🔴 Pourquoi cette table existe, alors qu'elle existe déjà côté front

Signalé le 31/08/2026, capture à l'appui : le courriel envoyé au syndic affichait

    Ticket #TK-079205 · CategorieTicket.panne · Soumis le 31/08/2026

`CategorieTicket` est une `(str, Enum)`, et depuis Python 3.11 son `__str__` rend
`CategorieTicket.panne` et non `panne`. Le gabarit recevait donc l'énumération
brute, et le destinataire lisait un identifiant de code Python.

⚠️ Les libellés vivaient **uniquement dans `front/src/lib/tickets.ts`**. Le
courriel est composé côté serveur : il n'y avait rien à afficher.

## La duplication est INÉVITABLE, et c'est documenté

Les contextes de construction Docker sont `./api` et `./front` : **rien de la
racine n'entre dans les images**. Un module partagé est donc impossible, et le
seul motif viable dans ce dépôt est *copie + test de concordance* — le même que
`perimetre_label` (front et API), verrouillé par `lint:libelle-perimetre`.

🔒 `api/tests/test_categories_ticket_concordance.py` lit la table du front et
exige que les deux disent la même chose. Sans lui, la copie diverge au premier
libellé retouché, et c'est le courriel — que personne ne relit — qui garde
l'ancien.
"""
from __future__ import annotations

#  ⚠️ Les VALEURS sont celles de `CategorieTicket` (`models/tickets.py`), les
#  libellés ceux de `CATEGORIES` (`front/src/lib/tickets.ts`). Les deux sont
#  vérifiés : la première liste par l'énumération, la seconde par le test de
#  concordance.
LIBELLES_CATEGORIE: dict[str, str] = {
    "panne": "Panne",
    "nuisance": "Nuisance",
    "question": "Question",
    "urgence": "Urgence",
    "bug": "Bug",
}


def libelle_categorie(categorie) -> str:
    """« panne » → « Panne ». Rend la valeur telle quelle si elle est inconnue.

    ⚠️ Accepte l'énumération ET la chaîne : le ticket porte l'une ou l'autre
    selon qu'il vient de la base ou d'un brouillon d'aperçu. Passer par
    `getattr(x, "value", x)` évite de le savoir — et c'est justement l'oubli de
    cette nuance qui a fait rendre `CategorieTicket.panne` dans un courriel.

    Une catégorie inconnue rend sa valeur brute plutôt qu'une chaîne vide : mieux
    vaut un mot non traduit qu'une ligne qui disparaît sans rien dire.
    """
    if not categorie:
        return ""
    valeur = str(getattr(categorie, "value", categorie))
    return LIBELLES_CATEGORIE.get(valeur, valeur)
