"""L'éligibilité d'une synthèse EST celle du carnet — jamais une copie (#1643).

Arbitré le 03/10/2026 : « uniquement les affaires du carnet sont éligibles ».
La règle vit dans `carnet_entretien` (`est_du_bati`, `contribue_au_carnet`) ;
une liste de catégories recopiée dans la synthèse, l'intervenant ou ailleurs
divergerait à la première catégorie ajoutée, et une affaire entrerait au carnet
sans synthèse — ou l'inverse — sans qu'aucun écran ne le montre.

Ce contrôle lit l'AST de `app/` :

1. `CATEGORIES_BATI` n'est lu que dans `utils/carnet_entretien.py` ;
2. le paquet `utils/synthese_affaire/` ne nomme aucune catégorie
   (`CategorieTicket`) et appelle bien `contribue_au_carnet`.
"""

from __future__ import annotations

import ast

from tests.aides_sources import module_app, modules_app

SOURCE = "utils/carnet_entretien.py"
PAQUET = "utils/synthese_affaire"


def _noms(arbre: ast.AST) -> set[str]:
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name):
            noms.add(noeud.id)
        elif isinstance(noeud, ast.Attribute):
            noms.add(noeud.attr)
        elif isinstance(noeud, ast.alias):
            noms.add(noeud.asname or noeud.name.rsplit(".", 1)[-1])
        elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            noms.add(noeud.name)
    return noms


def test_cas_zero_la_source_porte_la_regle():
    noms = _noms(module_app(SOURCE).arbre)
    assert {"CATEGORIES_BATI", "est_du_bati", "contribue_au_carnet"} <= noms


def test_categories_bati_ne_se_lit_que_dans_le_carnet():
    fautifs = [
        m.rel for m in modules_app() if m.rel != SOURCE and "CATEGORIES_BATI" in _noms(m.arbre)
    ]
    assert not fautifs, (
        "`CATEGORIES_BATI` lu hors du carnet — passer par `est_du_bati` ou "
        f"`contribue_au_carnet` : {fautifs}"
    )


def test_la_synthese_ne_nomme_aucune_categorie_et_appelle_le_carnet():
    modules = modules_app(PAQUET, minimum=5)
    fautifs = [m.rel for m in modules if "CategorieTicket" in _noms(m.arbre)]
    assert not fautifs, f"la synthèse nomme des catégories elle-même : {fautifs}"
    appels = [m.rel for m in modules if "contribue_au_carnet" in _noms(m.arbre)]
    assert appels, "aucun module de la synthèse n'appelle `contribue_au_carnet`"
