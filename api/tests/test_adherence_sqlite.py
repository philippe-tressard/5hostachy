"""L'adhérence du code à SQLite ne vit QUE dans `app/dialecte.py` (#1747).

Chantier multi-copropriétés, D4 : la plateforme passera sous PostgreSQL. Ce qui
lie le code à un moteur — `PRAGMA`, `sqlite_master`, une URL de base-fichier, une
fonction SQL propre à SQLite (`func.strftime`, `json_extract`…), le pilote
`sqlite3` — se demande au module de dialecte, sous un nom qui dit la QUESTION
(« vider le journal », « le mois de cette date »), jamais la commande.

Premier temps du lot : deux plafonds, 39 modules et 23 appels, qui ne
faisaient que baisser. Ils comptaient la PROSE — un commentaire qui raconte un
incident SQLite, un `.strftime` Python, un en-tête HTTP `Pragma` — et la règle
se lisait « moins de mots », pas « moins d'adhérence ». Le relevé lit désormais
l'AST : les chaînes exécutées (docstrings exclues, l'AST ignore les
commentaires), les appels `func.<fonction SQLite>` et les imports. Il en restait
quatorze modules ; tous passent par le dialecte.
"""

from __future__ import annotations

import ast
import re

from tests.aides_sources import chaines_du_code, module_app, modules_app

#: Le SEUL module qui nomme un moteur.
DIALECTE = "dialecte.py"

#: Une chaîne exécutée qui n'a de sens que pour SQLite. `PRAGMA` en majuscules
#: suivi d'un espace : l'en-tête HTTP `Pragma` n'en est pas un.
_CHAINE_SQLITE = re.compile(
    r"\bPRAGMA\s|sqlite_master|sqlite:|json_extract\(|julianday\(|group_concat\("
    r"|datetime\('now|strftime\('|insert\s+or\s+(ignore|replace)",
)
_INSENSIBLE = re.compile(r"insert\s+or\s+(ignore|replace)|json_extract\(", re.IGNORECASE)

#: Les fonctions SQL que seul SQLite connaît, appelées par `func.<nom>`.
FONCTIONS_SQLITE = frozenset({"strftime", "json_extract", "julianday", "group_concat"})


def adherences(arbre: ast.AST) -> list[tuple[int, str]]:
    """Ce qui, dans un arbre, ne vaut que pour SQLite : `(ligne, forme)`."""
    trouvees = [
        (n.lineno, n.value.strip()[:60])
        for n in chaines_du_code(arbre)
        if _CHAINE_SQLITE.search(n.value) or _INSENSIBLE.search(n.value)
    ]
    for n in ast.walk(arbre):
        if (
            isinstance(n, ast.Attribute)
            and n.attr in FONCTIONS_SQLITE
            and isinstance(n.value, ast.Name)
            and n.value.id == "func"
        ):
            trouvees.append((n.lineno, f"func.{n.attr}"))
        elif isinstance(n, ast.Import):
            trouvees += [(n.lineno, f"import {a.name}") for a in n.names if "sqlite" in a.name]
        elif isinstance(n, ast.ImportFrom) and "sqlite" in (n.module or ""):
            trouvees.append((n.lineno, f"from {n.module}"))
    return sorted(trouvees)


def test_aucune_adherence_a_sqlite_hors_du_dialecte():
    fautes = {m.rel: adherences(m.arbre) for m in modules_app(minimum=300) if m.rel != DIALECTE}
    fautes = {rel: a for rel, a in fautes.items() if a}
    assert not fautes, (
        "Adhérence à SQLite hors de `app/dialecte.py` (D4, #1747) — la demander au "
        "dialecte, sous un nom qui dit la question :\n"
        + "\n".join(
            f"  app/{rel}:{ligne} — {forme}" for rel, a in fautes.items() for ligne, forme in a
        )
    )


def test_le_dialecte_porte_ce_que_le_releve_cherche():
    """Le cas zéro : si le dialecte n'était plus vu, le relevé ne mesurerait plus rien."""
    formes = " ".join(f for _, f in adherences(module_app(DIALECTE).arbre))
    for attendu in ("PRAGMA foreign_keys", "PRAGMA quick_check", "sqlite:///"):
        assert attendu in formes, f"le relevé ne voit plus « {attendu} » dans le dialecte"


#: Chaque forme refusée, et ce qui ne l'est pas — la prose, l'en-tête HTTP, le
#: `.strftime` d'une date Python. Écrit en morceaux : ce fichier est lu par des
#: garde-fous qui cherchent ces formes dans les commandes.
_PILOTE = "sqlite" + "3"
_EXEMPLE = f'''
"""Docstring : PRAGMA quick_check, sqlite:///x, func.strftime — racontés, pas exécutés."""
import {_PILOTE}
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy import func, text

# commentaire : PRAGMA foreign_keys=ON
a = text("PRAGMA foreign_keys=ON")
b = text("SELECT sql FROM sqlite_master")
c = "sqlite:////base.db"
d = func.strftime("%Y-%m", x)
e = text("SELECT json_extract(x, '$.a')")
f = text("INSERT OR IGNORE INTO t VALUES (1)")
g = {{"Pragma": "no-cache"}}
h = maintenant.strftime("%Y-%m-%d")
i = func.count()
'''


def test_chaque_forme_est_reperee_et_la_prose_ne_l_est_pas():
    formes = [f for _, f in adherences(ast.parse(_EXEMPLE))]
    assert formes == [
        f"import {_PILOTE}",
        "from sqlalchemy.dialects.sqlite",
        "PRAGMA foreign_keys=ON",
        "SELECT sql FROM sqlite_master",
        "sqlite:////base.db",
        "func.strftime",
        "SELECT json_extract(x, '$.a')",
        "INSERT OR IGNORE INTO t VALUES (1)",
    ]
