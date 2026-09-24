"""Ce que le code importe, `requirements.txt` le déclare (24/09/2026, #1048).

`pydantic`, `pydantic_settings` et `sqlalchemy` étaient importés directement —
près de 300 fois à eux trois — sans figurer dans `requirements.txt` : ils
arrivaient par `fastapi`, `sqlmodel` et `fastapi-mail`. Une montée de l'un de
ceux-là pouvait donc changer leur version, voire les retirer, sans que le fichier
des dépendances bouge d'une ligne. Le dépôt épinglait tout, sauf ce dont il se
servait le plus.

Ce contrôle lit les `import` de `app/` et `alembic/` (le code qui tourne en
production), rattache chaque module tiers à sa distribution par les métadonnées
installées — `PIL` vient de `Pillow`, `jwt` de `PyJWT` : un nom de module n'est
pas un nom de paquet — et exige que cette distribution soit écrite dans
`requirements.txt`.

⚠️ Le sens inverse — un paquet déclaré que rien n'importe — ne se contrôle pas
ainsi : `python-dotenv` n'est jamais importé et sert pourtant (il lit le `.env`
de `pydantic-settings`), `uvicorn` et `bcrypt` sont chargés par leur nom. Chaque
ligne de `requirements.txt` qui n'est pas importée dit pourquoi elle est là.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys
from importlib.metadata import packages_distributions

RACINE = pathlib.Path(__file__).resolve().parents[1]
REQUIREMENTS = RACINE / "requirements.txt"
PORTEE = ("app", "alembic")


def _normaliser(nom: str) -> str:
    """PEP 503 : `SQLAlchemy`, `pydantic_settings` et `pydantic-settings` se valent."""
    return re.sub(r"[-_.]+", "-", nom).lower()


def _declarees() -> set[str]:
    noms = set()
    for ligne in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if not ligne or ligne.startswith("-"):
            continue
        noms.add(_normaliser(re.split(r"[\[=<>~!;\s]", ligne, maxsplit=1)[0]))
    return noms


def _modules_tiers() -> dict[str, set[str]]:
    """Module de premier niveau → fichiers qui l'importent, hors stdlib et `app`."""
    trouves: dict[str, set[str]] = {}
    for dossier in PORTEE:
        for chemin in (RACINE / dossier).rglob("*.py"):
            arbre = ast.parse(chemin.read_text(encoding="utf-8"))
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    noms = [a.name for a in noeud.names]
                elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
                    noms = [noeud.module]
                else:
                    continue
                for nom in noms:
                    tete = nom.split(".")[0]
                    if tete in sys.stdlib_module_names or tete == "app":
                        continue
                    trouves.setdefault(tete, set()).add(chemin.relative_to(RACINE).as_posix())
    return trouves


def test_cas_zero_le_parcours_voit_les_imports_et_le_fichier():
    """Sans quoi le contrôle ne verrait rien, et ne refuserait donc rien."""
    modules = _modules_tiers()
    assert {"fastapi", "sqlmodel", "pydantic"} <= modules.keys(), (
        f"le parcours de {PORTEE} ne voit plus les imports : {sorted(modules)}"
    )
    assert {"fastapi", "sqlmodel"} <= _declarees(), "`requirements.txt` n'est plus lu"


def test_tout_module_tiers_importe_vient_d_une_dependance_declaree():
    declarees = _declarees()
    distributions = packages_distributions()
    fautifs = {}
    for module, fichiers in sorted(_modules_tiers().items()):
        candidates = {_normaliser(d) for d in distributions.get(module, [])}
        if not candidates:
            fautifs[module] = f"module introuvable dans l'environnement — {sorted(fichiers)[:3]}"
        elif not candidates & declarees:
            fautifs[module] = (
                f"vient de {sorted(candidates)}, non déclaré — importé par {sorted(fichiers)[:3]}"
            )
    assert not fautifs, (
        "Des modules importés par le code ne sont pas déclarés dans requirements.txt :\n  "
        + "\n  ".join(f"{m} : {raison}" for m, raison in fautifs.items())
        + "\nLes déclarer et les épingler — une dépendance transitive peut changer "
        "de version, ou disparaître, au gré d'une autre."
    )
