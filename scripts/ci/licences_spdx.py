"""Expressions de licence SPDX et métadonnées Python — lecture et jugement.

Fonctions PURES, sans dépendance hors bibliothèque standard : elles sont
éprouvées par `licences_tierces.py --selftest`, et partagées avec
`contenus_tiers.py` (les identifiants que REUSE attribue à un fichier).

Ce module ne dit rien de juridique : il dit si une expression ne fait appel
qu'à des licences de la liste blanche (`licences_politique.ADMISES`). Ce qui
n'y est pas devient une EXCEPTION déclarée — jamais une décision prise ici.
"""

from __future__ import annotations

import re

OPERATEURS = {"AND", "OR", "WITH"}
_JETON = re.compile(r"\s*(\(|\)|[A-Za-z0-9.+:\-]+)")


def jetons(expression: str) -> list[str]:
    """Découpe une expression SPDX ; lève ValueError sur un caractère inattendu."""
    resultat: list[str] = []
    position = 0
    texte = expression.strip()
    while position < len(texte):
        trouve = _JETON.match(texte, position)
        if not trouve:
            raise ValueError(f"expression SPDX illisible : {expression!r}")
        jeton = trouve.group(1)
        resultat.append(jeton.upper() if jeton.upper() in OPERATEURS else jeton)
        position = trouve.end()
    if not resultat:
        raise ValueError("expression SPDX vide")
    return resultat


def identifiants(expression: str) -> set[str]:
    """Les licences nommées par l'expression (sans opérateurs ni exceptions WITH)."""
    elements = jetons(expression)
    noms: set[str] = set()
    for i, jeton in enumerate(elements):
        if jeton in OPERATEURS or jeton in ("(", ")"):
            continue
        if i > 0 and elements[i - 1] == "WITH":
            continue
        noms.add(jeton)
    return noms


def admise(expression: str, admises: frozenset[str] | set[str]) -> bool:
    """Vraie si l'expression se satisfait avec les seules licences admises.

    `A OR B` : il suffit qu'une branche le soit (le choix est offert) ;
    `A AND B` : il faut que toutes le soient ; `A WITH X` : jamais admise
    par défaut — une exception de licence se lit, elle ne se devine pas.
    Une expression illisible n'est PAS admise : elle devient une exception
    à déclarer, ce qui la met sous les yeux de quelqu'un.
    """
    try:
        elements = jetons(expression)
    except ValueError:
        return False
    position = 0

    def lire() -> str | None:
        return elements[position] if position < len(elements) else None

    def avancer() -> str:
        nonlocal position
        position += 1
        return elements[position - 1]

    def facteur() -> bool:
        jeton = lire()
        if jeton is None or jeton in OPERATEURS or jeton == ")":
            raise ValueError("opérande manquant")
        avancer()
        if jeton == "(":
            valeur = disjonction()
            if lire() != ")":
                raise ValueError("parenthèse non fermée")
            avancer()
            return valeur
        if lire() == "WITH":
            avancer()
            facteur()
            return False
        return jeton in admises

    def conjonction() -> bool:
        valeur = facteur()
        while lire() == "AND":
            avancer()
            valeur = facteur() and valeur
        return valeur

    def disjonction() -> bool:
        valeur = conjonction()
        while lire() == "OR":
            avancer()
            valeur = conjonction() or valeur
        return valeur

    try:
        resultat = disjonction()
    except ValueError:
        return False
    return resultat if position == len(elements) else False


# ── Métadonnées Python ──────────────────────────────────────────────────────
#  Trois sources, par ordre de confiance : `License-Expression` (PEP 639, SPDX
#  par construction), le champ libre `License` quand il est court, puis les
#  classifieurs. Un classifieur « BSD License » ne dit pas QUELLE BSD : il est
#  rendu tel quel (`BSD`), sans inventer de variante.
CLASSIFIEURS = {
    "MIT License": "MIT",
    "BSD License": "BSD",
    "Apache Software License": "Apache-2.0",
    "ISC License (ISCL)": "ISC",
    "The Unlicense (Unlicense)": "Unlicense",
    "Python Software Foundation License": "PSF-2.0",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "Mozilla Public License 1.1 (MPL 1.1)": "MPL-1.1",
    "GNU General Public License v2 or later (GPLv2+)": "GPL-2.0-or-later",
    "GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.0-or-later",
}
ALIAS_CHAMP = {
    "Apache License, Version 2.0": "Apache-2.0",
    "Apache 2.0": "Apache-2.0",
    "MIT License": "MIT",
}
CHAMP_COURT = 60


def licence_python(
    champ_expression: str | None, champ_licence: str | None, classifieurs: list[str]
) -> tuple[str, str]:
    """(expression, source) d'une distribution Python, d'après ses métadonnées."""
    if champ_expression and champ_expression.strip():
        return champ_expression.strip(), "License-Expression"
    texte = (champ_licence or "").strip()
    if texte and "\n" not in texte and len(texte) <= CHAMP_COURT:
        return ALIAS_CHAMP.get(texte, texte), "License"
    licences = [c.split(" :: ")[-1] for c in classifieurs if c.startswith("License ::")]
    licences = [c for c in licences if c != "OSI Approved"]
    if len(licences) == 1:
        return CLASSIFIEURS.get(licences[0], licences[0]), "Classifier"
    if licences:
        # Plusieurs classifieurs ne disent ni « au choix » ni « cumulées » :
        # l'expression est rendue ILLISIBLE exprès, donc jamais admise d'office.
        noms = " | ".join(CLASSIFIEURS.get(c, c) for c in licences)
        return f"{noms} (classifieurs multiples)", "Classifier"
    return "NON DÉTERMINÉE", "aucune"
