"""Calculs purs de la télémétrie — aucune session, aucune requête.

POURQUOI CE MODULE EXISTE (16/08/2026, #354). L'écran Admin → Télémétrie
affichait deux totaux côte à côte qui ne se réconciliaient pas — « 78 vues » d'un
côté, « 74 vues » de l'autre — et une colonne « UTILISATEURS » fausse. Rien de
tout cela n'était couvert : `dashboard()` est une fonction de 338 lignes qui mêle
requêtes et arithmétique, donc rien n'y était atteignable par un test.

Ce qui est arithmétique vit désormais ici, où un test peut l'exercer sans base ni
session. C'est la forme que `standards/04` §11 impose déjà aux décisions d'infra —
isoler la décision en fonction pure — appliquée à un calcul d'affichage.
"""

from __future__ import annotations

from collections.abc import Iterable


def uniques_par_page(paires: Iterable[tuple[str, int | None]]) -> dict[str, int]:
    """Nombre d'utilisateurs DISTINCTS par page, sur toute la période.

    `paires` est une suite de `(page, user_id)` — un couple par événement, tel que
    le rend une requête groupée. Les vues sans utilisateur (`None`) sont ignorées :
    elles existent, mais elles ne peuvent être attribuées à personne. C'est
    précisément ce que `vues_non_attribuees()` ci-dessous rend visible, au lieu de
    le laisser deviner.

    ⚠️ POURQUOI CETTE FONCTION REMPLACE UNE SOMME. Le code additionnait les
    compteurs journaliers de visiteurs distincts :

        top_pages[page]["uniques"] += ligne.utilisateurs_uniques

    Or **additionner des cardinalités de distincts ne donne pas la cardinalité de
    l'union**. Une page vue par la même personne trois jours de suite affichait
    « 3 utilisateurs » là où il n'y en a qu'un. Le défaut était invisible sur la
    capture d'origine — un seul jour était agrégé, donc la colonne valait 1
    partout — et se serait révélé tout seul en s'aggravant avec le temps.
    """
    par_page: dict[str, set[int]] = {}
    for page, user_id in paires:
        if user_id is None:
            continue
        par_page.setdefault(page, set()).add(user_id)
    return {page: len(users) for page, users in par_page.items()}


def vues_non_attribuees(total_vues: int, vues_attribuees: int) -> int:
    """Vues comptées dans le total mais rattachées à aucun utilisateur.

    C'est l'explication de l'écart que l'utilisateur a signalé : le tableau des
    pages compte **toutes** les vues, celui des utilisateurs seulement celles qui
    portent un `user_id`. Une vue enregistrée avant l'établissement de la session,
    ou après son expiration, n'appartient qu'au premier.

    Rendre ce nombre permet à l'écran de **dire** l'écart au lieu de le laisser
    deviner — le minimum que #354 exige : « soit les deux nombres se réconcilient,
    soit l'écran dit pourquoi ».

    Borné à zéro : les deux totaux peuvent venir de sources dont la fraîcheur
    diffère (agrégats de 02:00 d'un côté, événements bruts de l'autre), et un
    écart négatif afficherait un nombre absurde plutôt qu'un manque d'information.
    """
    return max(0, total_vues - vues_attribuees)
