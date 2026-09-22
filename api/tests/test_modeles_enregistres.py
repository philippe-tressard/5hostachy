"""Chaque module de `app/models/` est chargé par l'import que fait Alembic (#1046).

## Pourquoi

Une table n'existe pour SQLModel — donc pour `create_all` ET pour Alembic — que
si le module qui la définit a été importé. Un modèle posé dans un fichier que
personne n'importe ne lève rien : l'application démarre, et la table manque, sans
un mot.

## Ce qui enregistre réellement les tables (mesuré le 23/09/2026)

`alembic/env.py` n'importe qu'une chose : `app.models.core`. Cet import charge
**tous** les modules, par deux voies qui se cumulent :

1. `app/models/__init__.py`, exécuté en premier parce qu'il est le paquet ;
2. les ré-exports `# noqa: E402` au milieu de `core.py`.

⚠️ La seconde voie n'est donc PAS un simple confort de compatibilité : retirer
ces ré-exports sans rien mettre à la place retirerait ces tables de la vue
d'Alembic. C'est ce que ce test empêcherait de faire en silence (#1157).

🔴 L'audit du 19/09 lisait les deux voies comme « deux mécanismes, dont un de
trop ». Mesuré, `import app.models` seul n'en charge que 7 sur 21 : sans la
seconde voie, 14 modules ne seraient chargés par rien d'autre que les routeurs.
"""
from __future__ import annotations

import pkgutil
import subprocess
import sys
from pathlib import Path

RACINE_API = Path(__file__).resolve().parents[1]


def _modules_non_charges_apres(import_: str) -> tuple[list[str], int]:
    """Lance un interpréteur NEUF — celui des tests a déjà tout importé, et
    répondrait « tout est chargé » quoi qu'il arrive."""
    code = (
        "import sys, pkgutil\n"
        f"import {import_}\n"
        "import app.models as m\n"
        "noms = [i.name for i in pkgutil.iter_modules(m.__path__)]\n"
        "manquants = [n for n in noms if f'app.models.{n}' not in sys.modules]\n"
        "print('TOTAL=' + str(len(noms)))\n"
        "print('MANQUANTS=' + ','.join(manquants))\n"
    )
    sortie = subprocess.run(
        [sys.executable, "-W", "ignore", "-c", code],
        cwd=RACINE_API, capture_output=True, text=True, encoding="utf-8",
    )
    assert sortie.returncode == 0, f"l'import de {import_} échoue :\n{sortie.stderr[-800:]}"
    #  ⚠️ Des lignes BALISÉES, pas des positions : quand rien ne manque, la
    #  dernière ligne est vide et `splitlines()` la supprime — ma première
    #  rédaction lisait alors le total à la place des manquants.
    valeurs = dict(ligne.split("=", 1) for ligne in sortie.stdout.splitlines() if "=" in ligne)
    total = int(valeurs["TOTAL"])
    manquants = [n for n in valeurs.get("MANQUANTS", "").split(",") if n]
    return manquants, total


def test_l_import_d_alembic_charge_tous_les_modules_de_modeles():
    """🔴 Ce qu'Alembic voit est ce que `import app.models.core` charge."""
    manquants, total = _modules_non_charges_apres("app.models.core")
    #  Cas zéro : sans modules relevés, l'assertion suivante serait vide.
    assert total > 10, f"seulement {total} module(s) relevé(s) sous app/models/"
    assert not manquants, (
        f"{len(manquants)} module(s) de modèles que `import app.models.core` ne "
        f"charge pas : {manquants}.\nLeurs tables n'existent ni pour Alembic ni pour "
        "`create_all`. → les importer dans `app/models/__init__.py`."
    )


def test_env_py_n_a_pas_change_de_point_d_entree():
    """Le test précédent suppose qu'Alembic importe `app.models.core`. Si
    `env.py` change d'import, c'est CET import qu'il faut mesurer."""
    source = (RACINE_API / "alembic" / "env.py").read_text(encoding="utf-8")
    assert "import app.models.core" in source, (
        "`alembic/env.py` n'importe plus `app.models.core` : ce test mesure alors "
        "un autre chargement que celui d'Alembic. Le réaligner sur le nouvel import."
    )
