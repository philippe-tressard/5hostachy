"""Garde-fou : un module `X.py` et un paquet `X/` ne coexistent jamais.

Le 11/08/2026, la PR #295 a ajouté `app/routers/publications/` et
`app/utils/email/` — les paquets qui remplacent deux monolithes — **sans
supprimer** `publications.py` (653 l.) et `email.py` (618 l.). Le site a
continué de marcher, et c'est précisément ce qui rend le défaut dangereux :
quand les deux coexistent, Python charge le **paquet** et ignore le module. Les
1 271 lignes restantes sont mortes, mais elles se lisent, se cherchent et
s'éditent comme du code vivant. Une correction faite dans le mauvais fichier
n'aurait **aucun effet**, sans le moindre message d'erreur.

Aucun contrôle ne pouvait le voir :

  - le contrôle de modularité signale un fichier qui **grossit** ; celui-là a
    été abandonné sur place, à taille constante ;
  - les tests passent — ils exercent le paquet, qui est complet ;
  - la couverture ne baisse pas de façon visible : le module mort n'est jamais
    importé, donc jamais compté.

C'est un défaut trouvé à l'œil, dans un ticket (#300), pas par un contrôle.
D'où celui-ci.

Le test est statique : il regarde des noms de fichiers, n'importe rien et
n'exécute aucun code applicatif.
"""
import pathlib

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]
APP = RACINE / "api" / "app"


def _paires_masquees():
    """Rend les couples (module.py, paquet/) qui portent le même nom importable.

    On compare des noms au sein d'un MÊME répertoire parent : c'est exactement la
    condition dans laquelle l'un masque l'autre pour l'import Python.
    """
    paires = []
    for paquet in APP.rglob("*"):
        if not paquet.is_dir() or "__pycache__" in paquet.parts:
            continue
        if not (paquet / "__init__.py").exists():
            continue  # un répertoire sans __init__.py n'est pas un paquet importable
        jumeau = paquet.with_suffix(".py")
        if jumeau.exists():
            paires.append((jumeau, paquet))
    return paires


def test_aucun_module_masque_par_un_paquet_du_meme_nom():
    """Le cas de #300 : `publications.py` survivant à côté de `publications/`."""
    paires = _paires_masquees()
    if paires:
        detail = "\n".join(
            f"  - {m.relative_to(RACINE)} ({len(m.read_text(encoding='utf-8').splitlines())} l.) "
            f"est masqué par {p.relative_to(RACINE)}/"
            for m, p in paires
        )
        pytest.fail(
            "Un module est masqué par un paquet du même nom — Python charge le "
            "paquet, le fichier .py est du code mort qui se lit comme du code "
            "vivant :\n" + detail + "\n\nSupprimer le module, après avoir vérifié "
            "qu'aucun de ses symboles ne manque au paquet."
        )


def test_le_controle_regarde_reellement_l_arborescence():
    """Auto-contrôle : sans paquet trouvé, le test ci-dessus passerait pour rien.

    C'est le cas zéro de `standards/04-fiabilite-des-controles.md` §2 : un
    contrôle qui n'a rien pu examiner rend une liste vide, et une liste vide se
    lit comme « aucun problème ». Si un déplacement de répertoire rendait `APP`
    introuvable, le test précédent deviendrait vert **définitivement** et pour la
    pire des raisons.
    """
    assert APP.is_dir(), f"arborescence introuvable : {APP}"
    paquets = [
        d for d in APP.rglob("*")
        if d.is_dir() and (d / "__init__.py").exists() and "__pycache__" not in d.parts
    ]
    assert len(paquets) >= 5, (
        f"{len(paquets)} paquet(s) trouvé(s) sous {APP} — trop peu pour que le "
        "contrôle soit crédible ; l'arborescence a probablement changé."
    )
