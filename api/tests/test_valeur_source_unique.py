"""La valeur d'une énumération se lit par `utils/valeurs.valeur`, nulle part ailleurs.

Neuf copies de `getattr(x, "value", x)` jusqu'au 23/09/2026, et le défaut
qu'elles prévenaient est revenu par la dixième écriture, qui ne l'avait pas :
`str(categorie)` dans `kanban_tickets` (#1092). Voir `app/utils/valeurs.py`.

⚠️ L'idiome a TROIS écritures, et ce test n'en a d'abord vu qu'une :

    getattr(x, "value", x)
    x.value if hasattr(x, "value") else str(x)
    x.value if isinstance(x, MonEnum) else x

🔴 Et jusqu'au 02/10/2026, il lisait le code LIGNE PAR LIGNE : `ruff format`
coupe une expression conditionnelle trop longue à chaque `if` et `else`, et
les trois copies d'`admin/acces.py` — `.value` sur une ligne, `if hasattr(` sur
la suivante — lui étaient invisibles. Il rendait vert sur quatre copies (#1536).
Le relevé lit donc l'ARBRE SYNTAXIQUE : la mise en page n'y existe plus, et
les commentaires ni les docstrings n'y sont du code.
"""

from __future__ import annotations

import ast

from tests.aides_sources import module_app, modules_app

_SOURCE = "utils/valeurs.py"


def _est_appel(noeud: ast.AST, nom: str) -> bool:
    return isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) and noeud.func.id == nom


def _est_chaine_value(noeud: ast.AST) -> bool:
    return isinstance(noeud, ast.Constant) and noeud.value == "value"


def _garde_l_objet(test: ast.AST, objet: ast.AST) -> bool:
    """La condition interroge-t-elle `objet` sur sa nature d'énumération ?"""
    forme = ast.dump(objet)
    for n in ast.walk(test):
        if _est_appel(n, "hasattr") and len(n.args) == 2 and _est_chaine_value(n.args[1]):
            return True
        if _est_appel(n, "isinstance") and n.args and ast.dump(n.args[0]) == forme:
            return True
    return False


def _copies(arbre: ast.AST) -> list[int]:
    """Les numéros de ligne où l'idiome est réécrit, quelle que soit sa mise en page."""
    lignes = []
    for n in ast.walk(arbre):
        #  getattr(x, "value", …)
        if _est_appel(n, "getattr") and len(n.args) >= 2 and _est_chaine_value(n.args[1]):
            lignes.append(n.lineno)
        #  x.value if hasattr(x, "value") / isinstance(x, …) else …
        elif (
            isinstance(n, ast.IfExp)
            and isinstance(n.body, ast.Attribute)
            and n.body.attr == "value"
            and _garde_l_objet(n.test, n.body.value)
        ):
            lignes.append(n.lineno)
    return sorted(lignes)


def test_aucune_copie_de_l_idiome_hors_de_sa_source():
    modules = modules_app()
    fautes = [f"{m.rel}:{ligne}" for m in modules if m.rel != _SOURCE for ligne in _copies(m.arbre)]
    assert not fautes, (
        f"Valeur d'énumération relue à la main — employer `app.utils.valeurs.valeur` : {fautes}"
    )


def test_le_releve_voit_chaque_ecriture():
    def releve(code: str) -> int:
        return len(_copies(ast.parse(code)))

    assert releve('x = getattr(tk.statut, "value", tk.statut)\n') == 1
    assert releve('x = u.statut.value if hasattr(u.statut, "value") else str(u.statut)\n') == 1
    assert releve("x = d.statut.value if isinstance(d.statut, StatutDelegation) else d.statut\n")
    #  La forme que `ruff format` produit, et que le relevé ligne à ligne ratait (#1536).
    assert (
        releve(
            "x = {\n"
            '    "user_statut": user.statut.value\n'
            '    if user and hasattr(user.statut, "value")\n'
            "    else str(user.statut)\n"
            "    if user\n"
            '    else "?",\n'
            "}\n"
        )
        == 1
    )
    #  Citer l'idiome n'est pas l'écrire.
    assert releve('#  `getattr(x, "value", x)` évite de le savoir\n') == 0
    assert releve('"""x.value if hasattr(x, "value") else str(x)"""\n') == 0
    #  Un `.value` gardé par une AUTRE question n'est pas l'idiome.
    assert releve("x = r.value if r is not None else None\n") == 0


def test_la_source_est_vue_par_le_releve():
    #  L'exclusion de `utils/valeurs.py` doit servir : si le relevé n'y voyait
    #  plus rien, il ne verrait plus non plus les copies (le témoin, `standards/04` §2).
    assert _copies(module_app(_SOURCE).arbre), (
        f"Le relevé ne reconnaît plus l'idiome dans sa propre source `{_SOURCE}` : "
        "il ne mesure donc plus rien ailleurs."
    )
