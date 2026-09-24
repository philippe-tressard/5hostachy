"""La valeur d'une énumération se lit par `utils/valeurs.valeur`, nulle part ailleurs.

Neuf copies de `getattr(x, "value", x)` jusqu'au 23/09/2026, et le défaut
qu'elles prévenaient est revenu par la dixième écriture, qui ne l'avait pas :
`str(categorie)` dans `kanban_tickets` (#1092). Voir `app/utils/valeurs.py`.
"""

from __future__ import annotations

import pathlib
import re

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"
_MOTIF = re.compile(r"""getattr\([^,()]+,\s*["']value["']""")
_SOURCE = "utils/valeurs.py"


def _copies(texte: str) -> int:
    #  Les commentaires et docstrings peuvent CITER l'idiome : seul le code compte.
    code = [ligne for ligne in texte.splitlines() if not ligne.lstrip().startswith(("#", "`"))]
    return sum(len(_MOTIF.findall(ligne)) for ligne in code)


def test_aucune_copie_de_l_idiome_hors_de_sa_source():
    fichiers = [p for p in _APP.rglob("*.py") if "__pycache__" not in p.parts]
    assert len(fichiers) >= 40, "Portée cassée."
    fautes = [
        p.relative_to(_APP).as_posix()
        for p in fichiers
        if p.relative_to(_APP).as_posix() != _SOURCE and _copies(p.read_text(encoding="utf-8"))
    ]
    assert not fautes, (
        f"Valeur d'énumération relue à la main — employer `app.utils.valeurs.valeur` : {fautes}"
    )


def test_le_releve_voit_une_copie():
    assert _copies('x = getattr(tk.statut, "value", tk.statut)\n') == 1
    assert _copies('#  `getattr(x, "value", x)` évite de le savoir\n') == 0
