"""Le code de l'application, lu UNE fois pour tous les tests (#1495).

## Pourquoi cette aide existe (30/09/2026)

Soixante-huit fichiers de tests parcouraient `app/**/*.py` chacun à sa façon :
`rglob` puis filtre de `__pycache__` — ou pas —, lecture, `ast.parse`, et un
plancher de cas zéro choisi à la main (> 25, > 40, > 50, > 100), quand il y en
avait un. Chaque copie était correcte le jour de son écriture ; ensemble, elles
avaient déjà divergé sur ce qu'elles lisaient (`standards/05` §9, corollaire :
**une portée recopiée diverge**).

## Ce qu'elle garantit

- **Une seule portée** : tous les modules de `app/`, triés, sans `__pycache__`.
- **Un cas zéro intégré** : l'arbre entier compte au moins `PLANCHER_APP`
  modules, et chaque sous-dossier demandé au moins `minimum` — un chemin qui a
  bougé fait échouer le test qui le lit, au lieu de le rendre vert sur rien
  (`standards/04` §2).
- **Une lecture par session** : source et arbre syntaxique sont mis en cache.
  ⚠️ L'arbre est PARTAGÉ entre les tests : on le parcourt, on ne le modifie pas.
"""

from __future__ import annotations

import ast
import functools
import pathlib
from dataclasses import dataclass

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Le nombre de modules sous lequel `app/` n'est plus lu en entier. Il y en a
#: près de 300 : un plancher bas ne rate aucune croissance, et attrape la
#: portée cassée qui ne voit plus rien.
PLANCHER_APP = 100


@dataclass(frozen=True)
class Module:
    """Un module de `app/` : son chemin, son chemin relatif, son texte."""

    chemin: pathlib.Path
    rel: str  #: relatif à `app/`, séparateur « / » — `routers/tickets/crud.py`
    source: str

    @functools.cached_property
    def arbre(self) -> ast.Module:
        return ast.parse(self.source, filename=str(self.chemin))

    @property
    def lignes(self) -> list[str]:
        return self.source.splitlines()


@functools.lru_cache(maxsize=None)
def _tous() -> tuple[Module, ...]:
    modules = tuple(
        Module(p, p.relative_to(APP).as_posix(), p.read_text(encoding="utf-8"))
        for p in sorted(APP.rglob("*.py"))
        if "__pycache__" not in p.parts
    )
    assert len(modules) >= PLANCHER_APP, (
        f"`app/` ne compte que {len(modules)} module(s) lus (plancher {PLANCHER_APP}) : "
        "la portée des contrôles a changé, et ils ne mesurent plus rien."
    )
    return modules


def modules_app(sous_dossier: str = "", *, minimum: int = 1) -> tuple[Module, ...]:
    """Les modules de `app/` — ou d'un sous-dossier (`"routers"`, `"utils/email"`).

    Lève si la portée rend moins de `minimum` modules : c'est le cas zéro de
    chaque contrôle qui l'emploie, écrit une fois ici.
    """
    prefixe = f"{sous_dossier.strip('/')}/" if sous_dossier else ""
    trouves = tuple(m for m in _tous() if m.rel.startswith(prefixe))
    assert len(trouves) >= minimum, (
        f"`app/{prefixe}` ne rend que {len(trouves)} module(s) (plancher {minimum}) : "
        "le dossier a bougé, et le contrôle qui le lit ne mesure plus rien."
    )
    return trouves


def module_app(rel: str) -> Module:
    """Un module précis de `app/`, par son chemin relatif — ou lève s'il a disparu."""
    for m in _tous():
        if m.rel == rel:
            return m
    raise AssertionError(f"`app/{rel}` est introuvable : le contrôle vise un module disparu.")
