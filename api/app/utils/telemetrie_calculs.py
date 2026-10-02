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


def _cumul_par_page(lignes, uniques=None) -> dict[str, dict]:
    """Les vues cumulées par page — écrit UNE fois (14/09/2026, #779).

    🔴 Les deux relevés le faisaient chacun de leur côté, et ils ne comptaient
    PAS la même chose sous le même nom :

    * le relevé à 30 jours lisait `uniques` dans un décompte DISTINCT calculé à
      part (`uniques_map`) ;
    * le relevé à 10 ans ADDITIONNAIT `utilisateurs_uniques` mois par mois.

    La seconde sur-compte : quelqu'un qui visite en janvier et en février y
    figure deux fois. Ce n'est pas le même indicateur, et rien ne le disait —
    deux colonnes « uniques » côte à côte dans l'écran, dont une seule mérite
    son nom.

    ⚠️ La divergence est CONSERVÉE, pas corrigée : la trancher change des
    chiffres affichés, et cela se décide devant l'écran. Elle est désormais
    NOMMÉE par le paramètre — `uniques` fourni = décompte distinct, absent =
    cumul. C'est la seule façon de ne pas la refaire par inadvertance.
    """
    cumul: dict[str, dict] = {}
    for ligne in lignes:
        page = cumul.setdefault(ligne.page, {"page": ligne.page, "total": 0, "uniques": 0})
        page["total"] += ligne.total
        if uniques is None:
            page["uniques"] += ligne.utilisateurs_uniques
    if uniques is not None:
        for page, valeurs in cumul.items():
            valeurs["uniques"] = uniques.get(page, 0)
    return cumul


#: Ce qu'on ne sait pas dire d'une personne absente du relevé — une seule
#: formulation, parce que deux écrans qui disent « Inconnu » et « ? » laissent
#: croire à deux situations différentes.
_FICHE_INCONNUE = {
    "nom": "Inconnu",
    "derniere_connexion": None,
    "statut": None,
    "batiment_id": None,
}


def _palmares(lignes, fiches: dict[int, dict]) -> list[dict]:
    """La ligne d'un utilisateur dans un palmarès — écrite une fois.

    Elle l'était deux fois, dans le même fichier, à cent cinquante lignes
    d'écart : le jour et le mois. Six clés recopiées, dont quatre lues dans
    quatre dictionnaires distincts.
    """
    return [
        {**_FICHE_INCONNUE, **fiches.get(ligne[0], {}), "total": ligne[1], "pages": ligne[2]}
        for ligne in lignes
    ]
