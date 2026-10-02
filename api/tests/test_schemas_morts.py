"""Un schéma de `app/schemas*.py` que rien ne référence est supprimé (#1566).

`UserUpdate` et `TokenResponse` ont vécu dans `app/schemas.py` sans qu'aucun
routeur, aucun module ni aucun autre schéma ne les nomme — ni le client front,
ni l'OpenAPI (qui ne publie que les schémas portés par une route). Un schéma
mort a l'air d'un contrat : on le met à jour, on le lit, on le croit vrai.

Un schéma est vivant s'il est nommé ailleurs dans `app/` que dans sa propre
définition : un autre module, ou un autre schéma du même fichier (base, type
de champ). Ce contrôle ne dit rien du *placement* des schémas — leur
déplacement près de leur routeur est un autre lot (#1566, volet « déplacer »).
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
    assert {"TicketCreate", "LoginRequest"} <= declares.keys()


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
