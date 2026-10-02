"""Calculs purs de la télémétrie — aucune session, aucune requête.

POURQUOI CE MODULE EXISTE (16/08/2026, #354). L'écran Admin → Télémétrie
affichait deux totaux côte à côte qui ne se réconciliaient pas, et une colonne
« UTILISATEURS » fausse. Rien n'était couvert : `dashboard()` mêlait requêtes et
arithmétique, donc rien n'y était atteignable par un test. Ce qui est
arithmétique vit ici, où un test l'exerce sans base ni session — la forme que
`standards/04` §11 impose aux décisions d'infra, appliquée à un calcul
d'affichage.

🔴 DEPUIS LE 02/10/2026 (#1545), IL N'Y A PLUS DE PERSONNES À COMPTER.
L'événement ne porte plus d'identifiant : les visiteurs distincts par page
(`uniques_par_page`), les vues « non attribuées » (`vues_non_attribuees`) et le
palmarès des utilisateurs (`_palmares`) n'ont plus de matière et sont retirés
avec ce qu'ils affichaient. Ce qui reste compte des VUES.
"""

from __future__ import annotations


def _cumul_par_page(lignes) -> dict[str, dict]:
    """Les vues cumulées par page, sur des agrégats journaliers ou mensuels.

    Écrit UNE fois (14/09/2026, #779) : les relevés à 30 jours et à 10 ans le
    faisaient chacun de leur côté. Additionner des totaux de vues est juste —
    c'est additionner des personnes distinctes qui ne l'était pas (#354), et il
    n'y en a plus.
    """
    cumul: dict[str, dict] = {}
    for ligne in lignes:
        page = cumul.setdefault(ligne.page, {"page": ligne.page, "total": 0})
        page["total"] += ligne.total
    return cumul


def record(totaux: dict[str, int], cle: str) -> dict | None:
    """La période qui a compté le plus de vues — `{cle: période, "vues": n}`, ou `None`.

    Sert au « jour le plus actif » (30 jours) et aux records du jour et du mois
    (10 ans) : trois écritures du même `max`, qui choisissaient la période sur le
    nombre de visiteurs distincts tant qu'il existait.

    À égalité, la période la plus ANCIENNE : c'est elle qui a établi le record.
    """
    if not totaux:
        return None
    meilleure = min(totaux, key=lambda periode: (-totaux[periode], periode))
    return {cle: meilleure, "vues": totaux[meilleure]}
