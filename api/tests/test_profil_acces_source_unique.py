"""Le profil d'accès d'un document se lit à UN endroit (#1551, 02/10/2026).

Détaché de `test_autorisation.py`, qui passait les 500 lignes : ce contrôle est
le sien par la notion (une règle d'autorisation recopiée), pas par le fichier.
"""

import ast

from tests.aides_sources import modules_app


#: Où se lit le profil d'accès d'un document — fichier et fonction (#1551).
_SOURCE_PROFIL = ("utils/visibility/documents.py", "profil_admet")


def _lectures_du_profil(arbre: ast.AST) -> list[int]:
    """Les lignes qui LISENT `….roles_autorises` (une écriture n'est pas une règle)."""
    return [
        n.lineno
        for n in ast.walk(arbre)
        if isinstance(n, ast.Attribute)
        and n.attr == "roles_autorises"
        and isinstance(n.ctx, ast.Load)
    ]


def _lectures_du_profil_par_fonction():
    """(fichier, fonction englobante ou `<module>`, ligne), sur tout `app/`."""
    for module in modules_app():
        if "roles_autorises" not in module.source:
            continue
        dans_une_fonction = set()
        for fonction in ast.walk(module.arbre):
            if isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for ligne in _lectures_du_profil(fonction):
                    dans_une_fonction.add(ligne)
                    yield module.rel, fonction.name, ligne
        for ligne in set(_lectures_du_profil(module.arbre)) - dans_une_fonction:
            yield module.rel, "<module>", ligne


def test_le_profil_d_acces_d_un_document_se_lit_a_un_seul_endroit():
    """🔴 #1551 : `list_categories` recopiait mot pour mot la règle de `document_visible`.

    Le test précédent reconnaît une règle de visibilité à son NOM (`*_visible`…).
    Une copie écrite dans le corps d'un endpoint n'en a pas : `list_categories`
    recomposait `roles ∪ {statut}` et le comparait au profil, à côté de la
    source. Le jour où le profil apprend quelque chose (un périmètre, une date),
    l'écran listerait des catégories dont aucun document ne s'ouvre — ou l'inverse.

    On reconnaît donc la règle à son CONTENU, lu sur l'AST : lire
    `roles_autorises`. Partout dans `app/`, pas seulement les routeurs —
    `standards/05` §9, la portée fait partie du contrôle.
    """
    fichier, fonction = _SOURCE_PROFIL
    lectures = list(_lectures_du_profil_par_fonction())
    fautes = sorted(
        {f"  app/{f}:{ligne} ({n})" for f, n, ligne in lectures if (f, n) != _SOURCE_PROFIL}
    )
    assert not fautes, (
        "Le profil d'accès d'un document est lu hors de sa source :\n"
        + "\n".join(fautes)
        + f"\n\nAppeler `{fichier}::{fonction}` — une seule écriture, que la "
        "bibliothèque, la liste des catégories et toute autre lecture partagent."
    )
    #  Cas zéro : sans lecture à la source, l'absence de copie ne prouverait rien.
    assert (fichier, fonction) in {(f, n) for f, n, _ in lectures}, (
        f"`{fichier}::{fonction}` ne lit plus `roles_autorises` (ou a disparu) : "
        "la règle n'a plus de source, ou le détecteur est devenu aveugle"
    )
