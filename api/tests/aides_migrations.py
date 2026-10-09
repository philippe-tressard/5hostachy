"""Charger une migration Alembic comme un module, écrit une fois (#1495).

Les migrations ne sont pas un paquet importable (`alembic/versions/` n'a pas de
`__init__.py`, et leurs noms commencent par un chiffre) : un test qui veut lire
leurs constantes passe par `importlib`. Ces quatre lignes étaient recopiées dans
chaque fichier qui en avait besoin.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
from types import ModuleType

VERSIONS = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"

#: La dernière migration de l'HISTORIQUE, écrite pour SQLite seule (#1757, #1747).
#: Celles-là ne sont ni jugées par `test_migrations_compatibles`, ni rejouées sur
#: PostgreSQL : une base PostgreSQL naît du schéma initial (`utils/schema_initial`,
#: spec §4.3). Toutes les suivantes valent pour les deux moteurs.
DERNIERE_HISTORIQUE = 271


def chemin_migration(motif: str) -> pathlib.Path:
    """Le fichier de migration qui correspond à `motif` (`"0194_*.py"`, `"0243"`…), ou lève."""
    if not motif.endswith(".py"):
        motif = f"{motif}*.py"
    trouves = sorted(VERSIONS.glob(motif))
    assert len(trouves) == 1, f"`{motif}` désigne {len(trouves)} migration(s), il en faut une."
    return trouves[0]


def charger_migration(motif: str) -> ModuleType:
    """La migration désignée par `motif`, chargée comme un module.

    Sur PostgreSQL (`TESTS_BASE_URL`), une migration HISTORIQUE n'est pas
    rejouée : le test qui la charge est sauté, et le dit (#1747).
    """
    chemin = chemin_migration(motif)
    if os.environ.get("TESTS_BASE_URL") and int(chemin.name[:4]) <= DERNIERE_HISTORIQUE:
        import pytest

        pytest.skip(
            f"migration historique {chemin.name[:4]} écrite pour SQLite — sur PostgreSQL, "
            "le schéma initial (#1747)",
            allow_module_level=True,
        )
    spec = importlib.util.spec_from_file_location(f"migration_{chemin.stem}", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
