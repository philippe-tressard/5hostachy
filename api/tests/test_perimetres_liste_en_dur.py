"""Aucune liste de périmètres ne doit réapparaître dans le code.

Deux contrôles **statiques**, séparés des tests de comportement de
`test_perimetres_arbre.py` : ils ne montent aucune base, n'appellent aucune
règle et ne dépendent d'aucune fixture — ils lisent l'arbre syntaxique des
sources. Deux natures de contrôle, deux fichiers ; le second a été extrait du
premier le 02/09/2026, quand le plafond de modularité l'a refusé.

## Pourquoi statiques

Le couplage est implicite : rien, à l'exécution, ne signale qu'une quatrième
copie de la liste des périmètres est apparue (`standards/05`). Le défaut
d'origine, c'est justement ça — il y en avait **trois** exemplaires, et ils
avaient divergé.

⚠️ Ils travaillent sur l'AST et non sur le texte, et c'est délibéré : un
commentaire qui *explique* pourquoi « résidence » a disparu est légitime, et un
contrôle qui le refuserait pousserait à supprimer les explications plutôt que les
défauts.
"""
import ast
from pathlib import Path

RACINE_API = Path(__file__).resolve().parents[1]


def _constantes_texte_hors_docstring(fichier: Path) -> list[str]:
    """Les chaînes littérales du fichier, docstrings et commentaires exclus."""
    arbre_py = ast.parse(fichier.read_text(encoding="utf-8"))
    docstrings = set()
    for noeud in ast.walk(arbre_py):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            corps = getattr(noeud, "body", [])
            if (corps and isinstance(corps[0], ast.Expr)
                    and isinstance(corps[0].value, ast.Constant)
                    and isinstance(corps[0].value.value, str)):
                docstrings.add(id(corps[0].value))
    return [
        noeud.value
        for noeud in ast.walk(arbre_py)
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, str)
        and id(noeud) not in docstrings
    ]


def test_aucune_liste_de_perimetres_ne_subsiste_dans_le_code():
    """Les constantes supprimées ne doivent pas revenir, ici ou sous un autre nom.

    Une liste de périmètres dans le code, c'est le défaut d'origine : il y en avait
    trois exemplaires, et ils avaient divergé.
    """
    interdits = {"SCOPES_RESIDENCE", "_PERIMETRES_GLOBAUX", "PERIMETRE_LABELS"}
    fautifs = []
    for fichier in (RACINE_API / "app").rglob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            cibles = []
            if isinstance(noeud, ast.Assign):
                cibles = noeud.targets
            elif isinstance(noeud, ast.AnnAssign):
                cibles = [noeud.target]
            for cible in cibles:
                if isinstance(cible, ast.Name) and cible.id in interdits:
                    fautifs.append(f"{fichier.relative_to(RACINE_API)} → {cible.id}")
    assert not fautifs, "liste de périmètres réapparue : " + ", ".join(fautifs)


def test_les_regles_de_decision_ne_citent_aucun_code_de_perimetre():
    """`visibility`, `destinataires` et le fil ne connaissent plus aucun périmètre.

    Ils doivent fonctionner pour une copropriété sans AFUL et sans caves : ils ne
    peuvent donc pas nommer ces périmètres dans une décision. Sans ce contrôle, la
    tentation de « juste ajouter le cas » ferait revenir la liste par petits bouts.
    """
    #  ⚠️ `visibility` est un PAQUET depuis le 20/08/2026 (#547) : on surveille
    #  TOUS ses fragments, pas un fichier nommé. Pointer le seul `socle.py`
    #  laisserait une règle sortir du contrôle en changeant simplement de
    #  fragment — « la portée du contrôle fait partie du contrôle »
    #  (`standards/05` §9).
    surveilles = [
        *sorted((RACINE_API / "app" / "utils" / "visibility").glob("*.py")),
        RACINE_API / "app" / "utils" / "destinataires.py",
        RACINE_API / "app" / "routers" / "flux" / "evenements.py",
    ]
    #  🔴 CAS ZÉRO — un chemin qui ne désigne plus rien rendrait ce test vert sans
    #  rien lire. C'est arrivé au découpage : le fichier surveillé avait disparu.
    #  Il a échoué bruyamment ce jour-là ; qu'il continue de le faire.
    manquants = [f for f in surveilles if not f.is_file()]
    assert not manquants, f"fichier surveillé introuvable : {manquants}"
    assert len(surveilles) >= 5, (
        f"{len(surveilles)} fichier(s) surveillé(s) : le paquet `visibility` a-t-il "
        "été renommé ? Ce test ne mesurerait plus grand-chose."
    )
    codes = {"résidence", "parking", "cave", "aful"}
    fautifs = []
    for fichier in surveilles:
        for valeur in _constantes_texte_hors_docstring(fichier):
            if valeur.strip().lower() in codes:
                fautifs.append(f"{fichier.name} → « {valeur} »")
    assert not fautifs, "code de périmètre en dur dans une règle : " + ", ".join(fautifs)
