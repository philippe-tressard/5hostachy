r"""Aucun fichier Python de l'API ne lève d'avertissement de syntaxe à la compilation (#1604).

`api/app/models/courriel.py` portait une docstring non brute contenant `\Seen` :
Python 3.12+ écrit alors un `SyntaxWarning: invalid escape sequence` à CHAQUE
démarrage — et Ruff ne le voyait pas : `W605` n'est pas dans les règles que la CI
sélectionne par répertoire (`.github/workflows/ci.yml`), et `--select` sur la
ligne de commande écarte tout `extend-select` de `ruff.toml`. Ce test regarde le
fait : il COMPILE chaque fichier et refuse l'avertissement, quelle que soit la
règle de Ruff qui l'aurait vu.
"""

from __future__ import annotations

import pathlib
import warnings

API = pathlib.Path(__file__).resolve().parents[1]
DOSSIERS = ("app", "tests", "alembic", "scripts")
PLANCHER = 300  # il y en a plus de 650 : un plancher bas attrape la portée cassée


def _fichiers() -> list[pathlib.Path]:
    return sorted(
        p
        for d in DOSSIERS
        if (API / d).is_dir()
        for p in (API / d).rglob("*.py")
        if "__pycache__" not in p.parts
    )


def _avertissements(source: str, nom: str = "<source>") -> list[str]:
    """Les avertissements (syntaxe ou dépréciation d'échappement) levés en compilant `source`."""
    with warnings.catch_warnings(record=True) as vus:
        warnings.simplefilter("always")
        compile(source, nom, "exec")
    return [f"{nom}:{w.lineno} {w.message}" for w in vus]


def test_cas_zero_le_releve_voit_les_fichiers():
    assert len(_fichiers()) >= PLANCHER, f"le relevé ne voit que {len(_fichiers())} fichiers"


def test_aucun_avertissement_de_syntaxe_a_la_compilation():
    trouves = []
    for p in _fichiers():
        trouves += _avertissements(p.read_text(encoding="utf-8"), p.relative_to(API).as_posix())
    assert not trouves, (
        "Avertissements à la compilation (échappement invalide : préférer r'''...''') :\n  "
        + "\n  ".join(trouves)
    )


def test_le_controle_sait_REFUSER():
    """Le cas fautif : la docstring de `courriel.py` avant #1604. La brute, elle, passe."""
    fautif = '"""Acquitté (`\\Seen`) donc relevé."""\n'
    assert _avertissements(fautif), "le contrôle ne voit pas un échappement invalide"
    assert _avertissements("r" + fautif) == []
