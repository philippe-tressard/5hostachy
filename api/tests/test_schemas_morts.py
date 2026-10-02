"""Un schéma de `app/schemas*.py` que rien ne référence est supprimé (#1566).

`UserUpdate` et `TokenResponse` ont vécu dans `app/schemas.py` sans qu'aucun
routeur, aucun module ni aucun autre schéma ne les nomme — ni le client front,
ni l'OpenAPI (qui ne publie que les schémas portés par une route). Un schéma
mort a l'air d'un contrat : on le met à jour, on le lit, on le croit vrai.

Un schéma est vivant s'il est nommé ailleurs dans `app/` que dans sa propre
définition : un autre module, ou un autre schéma du même fichier (base, type
de champ). Le *placement* est tenu plus bas : un schéma qu'un seul routeur
emploie vit à côté de lui, jamais dans un fichier partagé.
"""

from __future__ import annotations

import ast
import re

from tests.aides_sources import modules_app


def _schemas_declares() -> dict[str, str]:
    """Nom de chaque classe de `app/schemas*.py` → fichier qui la déclare."""
    return {
        n.name: m.rel
        for m in modules_app()
        if re.fullmatch(r"schemas(_\w+)?\.py", m.rel)
        for n in m.arbre.body
        if isinstance(n, ast.ClassDef)
    }


def _morts(declares: dict[str, str], sources: dict[str, str]) -> list[str]:
    """Les classes nommées nulle part ailleurs que sur leur ligne `class X`."""
    morts = []
    for nom, fichier in sorted(declares.items()):
        motif = re.compile(rf"\b{re.escape(nom)}\b")
        autres = sum(len(motif.findall(s)) for f, s in sources.items() if f != fichier)
        propres = len(motif.findall(sources[fichier]))  # la définition compte pour 1
        if autres == 0 and propres <= 1:
            morts.append(f"app/{fichier} : {nom}")
    return morts


def test_cas_zero_le_releve_voit_les_schemas_et_les_sources():
    declares = _schemas_declares()
    assert len(declares) > 10, f"le relevé ne voit plus les schémas : {sorted(declares)}"
    assert {"TicketCreate", "UserRead"} <= declares.keys()


def test_aucun_schema_mort():
    sources = {m.rel: m.source for m in modules_app()}
    morts = _morts(_schemas_declares(), sources)
    assert not morts, "Schémas que rien ne référence — les supprimer :\n  " + "\n  ".join(morts)


def test_le_controle_des_schemas_morts_sait_REFUSER():
    """Le cas fautif : une classe jamais nommée ailleurs. Une classe utilisée ne l'est pas."""
    sources = {
        "schemas.py": "class Mort(BaseModel):\n  a: int\nclass Base(BaseModel):\n  a: int\n"
        "class Vivant(Base):\n  b: int\n",
        "routers/x.py": "from app.schemas import Vivant\n",
    }
    declares = {"Mort": "schemas.py", "Base": "schemas.py", "Vivant": "schemas.py"}
    #  `Base` est nommée par `Vivant` (même fichier), `Vivant` par un routeur.
    assert _morts(declares, sources) == ["app/schemas.py : Mort"]


# ── Un schéma qu'un seul routeur emploie vit à côté de lui (#1566) ───────────


def _noms_dans_les_classes(modules) -> dict[str, set[str]]:
    """Pour chaque classe de `schemas*.py`, les noms qu'emploient les AUTRES classes de ces fichiers.

    Base, type de champ, validateur : un schéma ainsi composé est PARTAGÉ par
    construction — il ne peut pas vivre à côté d'un routeur sans que les autres
    schémas n'importent ce routeur.
    """
    emplois: dict[str, set[str]] = {}
    for m in modules:
        for classe in (n for n in m.arbre.body if isinstance(n, ast.ClassDef)):
            noms = {n.id for n in ast.walk(classe) if isinstance(n, ast.Name)}
            emplois[classe.name] = noms - {classe.name}
    return emplois


def _mono_routeur(modules_schemas, sources: dict[str, str]) -> list[str]:
    """Les classes de `schemas*.py` que UN SEUL module hors `schemas*.py` nomme, sans qu'aucun
    autre schéma ne les compose : elles auraient leur place à côté de ce module."""
    emplois = _noms_dans_les_classes(modules_schemas)
    declares = {
        n.name: m.rel for m in modules_schemas for n in m.arbre.body if isinstance(n, ast.ClassDef)
    }
    hors_schemas = {r: s for r, s in sources.items() if r not in {m.rel for m in modules_schemas}}
    mono = []
    for nom, fichier in sorted(declares.items()):
        compose = any(nom in noms for autre, noms in emplois.items() if autre != nom)
        motif = re.compile(rf"\b{re.escape(nom)}\b")
        users = sorted(r for r, s in hors_schemas.items() if motif.search(s))
        if len(users) == 1 and not compose:
            mono.append(f"app/{fichier} : {nom} → seul {users[0]} s'en sert")
    return mono


def _modules_schemas():
    return [m for m in modules_app() if re.fullmatch(r"schemas(_\w+)?\.py", m.rel)]


def test_aucun_schema_partage_n_a_qu_un_seul_routeur():
    """Plafond : zéro. Il en restait huit au 02/10/2026, tous déplacés."""
    sources = {m.rel: m.source for m in modules_app()}
    mono = _mono_routeur(_modules_schemas(), sources)
    assert not mono, (
        "Schémas propres à un seul module, rangés dans un fichier partagé — les déplacer "
        "à côté de lui (`<routeur>_schemas.py`) :\n  " + "\n  ".join(mono)
    )


def test_le_releve_mono_routeur_sait_REFUSER():
    """Le cas fautif : une classe qu'un seul routeur nomme et qu'aucun schéma ne compose."""

    class _Mod:
        def __init__(self, rel, source):
            self.rel = rel
            self.source = source
            self.arbre = ast.parse(source)

    schemas = [
        _Mod(
            "schemas.py",
            "class Seul(BaseModel):\n  a: int\n"
            "class Brique(BaseModel):\n  a: int\n"
            "class Partage(BaseModel):\n  b: Brique\n"
            "class Deux(BaseModel):\n  a: int\n",
        )
    ]
    sources = {
        "schemas.py": schemas[0].source,
        "routers/a.py": "from app.schemas import Seul, Partage, Deux\n",
        "routers/b.py": "from app.schemas import Partage, Brique, Deux\n",
    }
    #  `Seul` : un routeur, aucun schéma → refusé. `Brique` : composée par `Partage`.
    #  `Partage` et `Deux` : deux routeurs.
    assert _mono_routeur(schemas, sources) == [
        "app/schemas.py : Seul → seul routers/a.py s'en sert"
    ]
