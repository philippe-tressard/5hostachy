"""L'adhérence du code à SQLite ne grandit plus (#1747, 09/10/2026).

Chantier multi-copropriétés, D4 : la plateforme passera sous PostgreSQL. Ce qui
lie le code à SQLite — `PRAGMA`, `sqlite_master`, les fonctions SQL propres à
SQLite écrites en clair — est autant de travail à défaire avant d'y arriver.

Ce contrôle ne le défait pas : il l'EMPÊCHE DE CROÎTRE. Deux plafonds, qui ne font
que baisser — comme `PLAFOND_404_BRUTS` ou `PLAFOND_CLONES` :

- `PLAFOND_MODULES` : les modules d'`app/` qui nomment SQLite ou un `PRAGMA` ;
- `PLAFOND_FONCTIONS` : les appels à une fonction SQL propre à SQLite
  (`json_extract`, `strftime`, `group_concat`, `datetime('now')`,
  `INSERT OR IGNORE|REPLACE`).

Un module qui s'en libère fait baisser le compte : le plafond se baisse dans le
même commit, sinon la place libérée se reprendrait sans un mot. La mesure de ce
qui casse VRAIMENT sur PostgreSQL est le workflow « PostgreSQL ».
"""

from __future__ import annotations

import re

from tests.aides_sources import modules_app

#: Relevé du 09/10/2026. Il ne fait que BAISSER.
PLAFOND_MODULES = 39
PLAFOND_FONCTIONS = 23

_NOMME_SQLITE = re.compile(r"sqlite|PRAGMA", re.IGNORECASE)
_FONCTION_SQLITE = re.compile(
    r"json_extract|datetime\('now|strftime\(|group_concat|insert or (ignore|replace)",
    re.IGNORECASE,
)


def releve() -> tuple[list[str], int]:
    modules = modules_app()
    nomment = sorted(m.rel for m in modules if _NOMME_SQLITE.search(m.source))
    fonctions = sum(len(_FONCTION_SQLITE.findall(m.source)) for m in modules)
    return nomment, fonctions


def test_l_adherence_a_sqlite_ne_grandit_pas():
    nomment, fonctions = releve()
    assert len(nomment) <= PLAFOND_MODULES, (
        f"{len(nomment)} modules nomment SQLite ou un PRAGMA (plafond {PLAFOND_MODULES}) : "
        "le code s'éloigne de PostgreSQL (D4). Passer par SQLAlchemy plutôt que par du SQL "
        "propre à SQLite."
    )
    assert fonctions <= PLAFOND_FONCTIONS, (
        f"{fonctions} appels à une fonction SQL propre à SQLite (plafond {PLAFOND_FONCTIONS})."
    )


def test_le_plafond_suit_la_baisse():
    nomment, fonctions = releve()
    assert len(nomment) == PLAFOND_MODULES, (
        f"{len(nomment)} modules nomment SQLite : baisser PLAFOND_MODULES à {len(nomment)}."
    )
    assert fonctions == PLAFOND_FONCTIONS, (
        f"{fonctions} appels SQLite : baisser PLAFOND_FONCTIONS à {fonctions}."
    )


def test_le_releve_voit_ce_qu_on_sait():
    """Témoin : `database.py` pose ses PRAGMA ; s'il n'était plus vu, le relevé est cassé."""
    nomment, _ = releve()
    assert "database.py" in nomment
    assert _FONCTION_SQLITE.search("SELECT json_extract(x, '$.a')")
    assert not _FONCTION_SQLITE.search("SELECT x FROM t")
