"""Corriger le périmètre d'une entrée d'historique, sans raturer le fil.

## La demande (01/09/2026, à l'écran)

> *« L'édition peut modifier le périmètre (correction d'erreur d'affectation
> d'un périmètre) à corriger pour toutes les pages ayant un périmètre qui
> devient éditable »*

## 🔴 Ce que cela renverse, et pourquoi c'est justifié

`TicketEvolutionUpdate` refusait `perimetre_cible`, avec ce commentaire :

> *« un périmètre déclaré est un fait daté. On en déclare un nouveau, on ne
> rature pas l'ancien — sinon l'historique du resserrement, qui est tout
> l'intérêt, disparaît. »*

Le raisonnement vaut pour un **resserrement** — « finalement, c'est le hall du
bâtiment 3 » — et il ne vaut pas pour une **faute de clic**. Or les deux
s'écrivent pareil, et la seconde coûte cher : le périmètre d'une entrée
**écrase celui du ticket** (`evolutions.py`, création). Une erreur d'affectation
reclasse donc tout le ticket, et le seul recours était d'écrire un second
commentaire pour dire que le premier s'était trompé.

L'arbitrage rendu est celui de l'utilisateur, et il porte sur son produit.

## ⚠️ La subtilité qui fait qu'une correction n'est pas une écriture

Corriger une entrée **ancienne** ne doit pas défaire une précision **récente** :
si trois commentaires ont resserré le périmètre et qu'on corrige le premier, le
ticket doit garder ce que le troisième a dit.

D'où la règle : *la correction ne se propage à l'objet que si l'entrée corrigée
est la dernière à avoir précisé quelque chose.* C'est exactement la règle de
lecture du front (`perimetreHerite`), appliquée à l'écriture.

Sans elle, corriger une vieille faute de frappe reclasserait le ticket sur un
périmètre abandonné depuis — un défaut silencieux, qui ne se verrait que sur la
liste filtrée.
"""
from __future__ import annotations

import json
from typing import Any, Optional, Sequence


def _cible(entree: Any) -> Optional[list]:
    """Le `perimetre_cible` d'une entrée, décodé — `None` si elle n'a rien dit."""
    brut = getattr(entree, "perimetre_cible", None)
    if not brut:
        return None
    if isinstance(brut, list):
        return brut or None
    try:
        valeur = json.loads(brut)
    except (TypeError, ValueError):
        return None
    return valeur or None


def doit_propager(entree: Any, toutes: Sequence[Any]) -> bool:
    """L'entrée corrigée est-elle la DERNIÈRE à avoir précisé un périmètre ?

    `toutes` est le fil complet, dans l'ordre chronologique. Une entrée qui n'a
    rien précisé ne compte pas — elle n'a rien changé.

    ⚠️ Le cas zéro compte : un fil vide ou une entrée absente rend `False`, donc
    on ne touche pas à l'objet. Ne jamais rendre `True` par défaut — la valeur
    sûre est celle qui n'écrit pas.
    """
    if _cible(entree) is None:
        #  On vient d'effacer le périmètre de cette entrée : elle ne dit plus
        #  rien, donc elle n'a plus rien à imposer à l'objet.
        return False
    identifiant = getattr(entree, "id", None)
    if identifiant is None:
        return False
    derniere = None
    for e in toutes:
        if _cible(e) is not None:
            derniere = getattr(e, "id", None)
    return derniere == identifiant


def _selftest() -> None:
    """Trois cas qui se ressemblent, et dont deux sont contre-intuitifs."""

    class E:
        def __init__(self, id, cible):
            self.id = id
            self.perimetre_cible = json.dumps(cible) if cible else None

    a, b, c = E(1, ["bat:1"]), E(2, None), E(3, ["bat:2"])
    #  1. La dernière qui a précisé : elle propage.
    assert doit_propager(c, [a, b, c])
    #  2. Une ancienne qui a précisé : elle ne défait pas la plus récente.
    assert not doit_propager(a, [a, b, c])
    #  3. Seule à avoir précisé, même suivie d'entrées muettes : elle propage.
    assert doit_propager(a, [a, b])
    #  4. Une entrée qui ne dit plus rien n'impose rien.
    assert not doit_propager(b, [a, b, c])
    #  5. Cas zéro : fil vide, entrée sans identifiant.
    assert not doit_propager(a, [])
    assert not doit_propager(E(None, ["bat:1"]), [])
    print("OK perimetre_fil : 6 cas verifies.")


if __name__ == "__main__":
    _selftest()
