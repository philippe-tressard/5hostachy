"""Un point d'entrée qui FACTURE est borné — sans exception (#1299).

## Pourquoi

Un appel au fournisseur d'IA (`utils.llm.demander`) se lit sur une facture.
Partout ailleurs, une requête en trop coûte du CPU ; ici un double-clic, une
tempête de réessais ou un onglet qui se recharge se paient. La limite sur la
synthèse de contrat avait été écrite le 15/09/2026, sur une branche jamais
fusionnée : `main` n'en portait aucune, sur aucun des trois points d'entrée.

## Ce que ce test mesure

1. les fonctions de `app/` qui appellent `demander` — relevées dans le code,
   jamais recopiées : un nouvel usage de l'IA y entre sans qu'on y pense ;
2. toute ROUTE qui appelle l'une d'elles, ou `demander` directement, porte
   `@limiter.limit(LIMITE_APPEL_FACTURE)`, sous son décorateur de route, et
   reçoit une `request` (sans elle, slowapi lève au premier appel).

⚠️ Deux niveaux d'appel, pas davantage : une route qui atteindrait `demander`
par trois fonctions intermédiaires lui échapperait. Le cas zéro l'empêche de
mesurer à vide — il exige de trouver au moins une route facturée.
"""

from __future__ import annotations

import ast
import pathlib

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"
_CIBLE = "demander"
_LIMITE = "LIMITE_APPEL_FACTURE"


def _arbres() -> dict[pathlib.Path, ast.Module]:
    return {f: ast.parse(f.read_text(encoding="utf-8")) for f in sorted(_APP.rglob("*.py"))}


def _appels(fonction: ast.AST) -> set[str]:
    noms = set()
    for n in ast.walk(fonction):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                noms.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                noms.add(n.func.attr)
    return noms


def _fonctions(arbre: ast.Module):
    return [n for n in ast.walk(arbre) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _est_route(f) -> bool:
    return any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Attribute)
        and d.func.attr in {"get", "post", "put", "patch", "delete"}
        for d in f.decorator_list
    )


def routes_facturees() -> dict[str, ast.AST]:
    arbres = _arbres()
    facturantes = {_CIBLE} | {
        f.name
        for chemin, a in arbres.items()
        if chemin.parent.name != "routers"
        for f in _fonctions(a)
        if f.name != _CIBLE and _CIBLE in _appels(f)
    }
    return {
        f"{chemin.relative_to(_APP)}::{f.name}": f
        for chemin, a in arbres.items()
        for f in _fonctions(a)
        if _est_route(f) and _appels(f) & facturantes
    }


def test_toute_route_facturee_est_bornee():
    routes = routes_facturees()
    assert routes, "aucune route n'appelle le fournisseur d'IA — le contrôle ne mesure rien"
    fautes = []
    for nom, f in routes.items():
        decores = [ast.unparse(d) for d in f.decorator_list]
        limites = [i for i, d in enumerate(decores) if "limiter.limit" in d]
        if not limites or _LIMITE not in decores[limites[0]]:
            fautes.append(f"{nom} : pas de @limiter.limit({_LIMITE})")
            continue
        if limites[0] < min(i for i, d in enumerate(decores) if "router." in d):
            fautes.append(f"{nom} : @limiter.limit posé AU-DESSUS de la route (sans effet)")
        if "request" not in [a.arg for a in f.args.args]:
            fautes.append(f"{nom} : limitée sans paramètre `request`")
    assert not fautes, "Appel facturé non borné :\n  " + "\n  ".join(fautes)


def test_les_trois_routes_connues_sont_vues():
    """Le relevé retrouve les trois points d'entrée facturés du 25/09/2026."""
    noms = {n.split("::")[1] for n in routes_facturees()}
    assert {"proposer_synthese", "proposer_description", "llm_test"} <= noms, noms
