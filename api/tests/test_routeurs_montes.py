"""Tout `APIRouter` déclaré sous `app/routers/` est monté dans l'application (#1046).

## Pourquoi

Un fichier de routes oublié dans `main.py` ne lève RIEN : l'import réussit,
l'application démarre, et les écrans qui appellent ces routes reçoivent 404.
L'audit du 19/09/2026 le relevait : `test_routes_uniques` et
`test_endpoints_orphelins` n'échoueraient pas sur un routeur oublié, et
`test_demarrage` ne garde qu'un PLANCHER de chemins — il attrape la disparition
d'un pan entier, pas celle d'un fichier.

Le risque a grandi au fil des découpages : chaque extraction « au fil de l'eau »
(`copropriete_patrimoine`, `calendrier_historique`, `auth_profil`…) crée un
routeur de plus qu'il faut penser à inclure. Le dépôt en compte aujourd'hui
plusieurs dizaines.

## Comment il mesure

Cette version de FastAPI n'aplatit plus les routes incluses : `app.routes` rend
des `_IncludedRouter` opaques (voir `test_demarrage.py`). On descend donc par
`original_router`, récursivement, et on relève l'IDENTITÉ de chaque routeur
atteint. Un routeur déclaré au niveau d'un module et absent de cet ensemble
n'est joignable par aucune URL.

🔴 `original_router` est un attribut PRIVÉ. S'il disparaît à une montée de
version, ce test ÉCHOUE — il ne se saute pas. Un contrôle qui ne peut plus
s'exécuter rend INCONNU, jamais OK (`standards/04` §1) : se taire ici, ce serait
annoncer « tout est monté » sans avoir rien vérifié.
"""
from __future__ import annotations

import importlib
import pkgutil

import pytest
from fastapi import APIRouter

import app.routers as paquet_routeurs
from app.main import app

#: Les routeurs volontairement NON montés, avec leur raison. Une exception non
#: écrite n'est pas une exception, c'est un oubli qui ressemble à une décision ;
#: et une exception qui cesse de servir fait échouer le test (voir plus bas).
EXCEPTIONS: dict[str, str] = {}


def _routeurs_declares() -> dict[str, APIRouter]:
    """Chaque `APIRouter` défini au niveau d'un module de `app/routers/`."""
    trouves: dict[str, APIRouter] = {}
    for info in pkgutil.walk_packages(paquet_routeurs.__path__, paquet_routeurs.__name__ + "."):
        module = importlib.import_module(info.name)
        for nom, valeur in vars(module).items():
            #  Seuls les routeurs DÉFINIS ici : un routeur importé d'ailleurs
            #  (`from .parc import router as …`) serait compté deux fois.
            if isinstance(valeur, APIRouter) and _defini_dans(valeur, module):
                trouves[f"{info.name}.{nom}"] = valeur
    return trouves


def _defini_dans(routeur: APIRouter, module) -> bool:
    """Un routeur « appartient » au module où ses routes sont déclarées.

    Un routeur vide (paquet agrégateur) appartient au module qui l'expose sous
    le nom `router` — c'est la convention de tous les `__init__.py` du dépôt.
    """
    for route in routeur.routes:
        point = getattr(route, "endpoint", None)
        if point is not None:
            return getattr(point, "__module__", None) == module.__name__
    return True


def _routeurs_atteints() -> set[int]:
    atteints: set[int] = set()

    def descendre(routes) -> None:
        for route in routes:
            if type(route).__name__ != "_IncludedRouter":
                continue
            if not hasattr(route, "original_router"):
                pytest.fail(
                    "`_IncludedRouter` n'a plus d'attribut `original_router` — FastAPI "
                    "a changé sa représentation interne, et ce contrôle ne peut plus "
                    "mesurer quels routeurs sont montés. INCONNU n'est pas OK : il faut "
                    "le réécrire, pas le sauter."
                )
            routeur = route.original_router
            if id(routeur) in atteints:
                continue
            atteints.add(id(routeur))
            descendre(routeur.routes)

    descendre(app.routes)
    return atteints


def test_le_controle_mesure_quelque_chose():
    """Cas zéro : sans routeurs déclarés ni atteints, le test suivant serait vert
    sans avoir rien comparé."""
    declares = _routeurs_declares()
    atteints = _routeurs_atteints()
    assert len(declares) > 30, f"seulement {len(declares)} routeur(s) déclaré(s) relevé(s)"
    assert len(atteints) > 30, f"seulement {len(atteints)} routeur(s) atteint(s) depuis l'application"


def test_tout_routeur_declare_est_monte():
    atteints = _routeurs_atteints()
    orphelins = sorted(
        nom for nom, r in _routeurs_declares().items()
        if id(r) not in atteints and nom not in EXCEPTIONS
    )
    assert not orphelins, (
        f"{len(orphelins)} routeur(s) déclaré(s) mais montés NULLE PART — leurs URL "
        "rendent 404, et rien d'autre ne le dit :\n  "
        + "\n  ".join(orphelins)
        + "\n\n  → `app.include_router(<module>.router)` dans `main.py`, ou dans le "
        "`__init__.py` du paquet qui le porte. S'il doit rester hors ligne, le "
        "déclarer dans EXCEPTIONS avec sa raison."
    )


def test_les_exceptions_servent_encore():
    """Une exception qui ne correspond plus à rien est une règle qui a changé
    sans que personne ne relise la liste."""
    declares = _routeurs_declares()
    atteints = _routeurs_atteints()
    mortes = [
        nom for nom in EXCEPTIONS
        if nom not in declares or id(declares[nom]) in atteints
    ]
    assert not mortes, f"exceptions à retirer : {mortes}"
