"""Le format d'un document imprimable se déclare à UN endroit — A4 par défaut.

## Pourquoi ce contrôle (18/09/2026)

Trois documents imprimables, trois blocs `@page` écrits à la main : le manuel en
A4 avec son pied numéroté, l'annonce de hall dans le format que son débordement
lui impose, la fiche d'arrivant en A4 avec des marges plus serrées. Le format
était donc « A4 par défaut » **par répétition**, pas par règle — et un quatrième
document aurait hérité de ce que le moteur choisit, pas de ce que la maison veut.

Demandé par Philippe : *« sauf Annonce Hall qui utilise des formats plus petits,
il faudrait fixer le format A4 par défaut »*. `pdf_theme.regle_page()` le fixe,
et ce test refuse qu'on le réécrive ailleurs.

## Ce qu'il laisse passer, et pourquoi

Les pages **nommées** — `@page garde` pour la couverture du manuel — ne
déclarent pas un format : elles surchargent les marges d'une page particulière
d'un document dont le format est déjà fixé. Les interdire obligerait à faire
passer par le thème une décision qui n'appartient qu'à ce document-là.
"""
from __future__ import annotations

import pathlib
import re

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"
SOURCE = "utils/pdf_theme.py"

#: `@page` SANS nom : c'est celui-là qui porte le format du document.
#: `@page garde {` ne correspond pas — le nom précède l'accolade.
PAGE_ANONYME = re.compile(r"@page\s*\{")


def _fichiers() -> list[pathlib.Path]:
    return [p for p in RACINE.rglob("*.py") if "__pycache__" not in p.parts]


def test_la_regle_de_page_existe_et_rend_de_l_A4():
    """Cas zéro : sans elle, tout ce fichier ne mesurerait rien."""
    from app.utils.pdf_theme import FORMAT_PAR_DEFAUT, regle_page

    assert FORMAT_PAR_DEFAUT == "A4"
    rendu = regle_page()
    assert "@page {" in rendu
    assert "size: A4;" in rendu, rendu
    assert "counter(page)" in rendu, "le pied numéroté a disparu du défaut"


def test_une_affiche_peut_choisir_son_format_et_renoncer_au_pied():
    """L'exception de l'annonce de hall, éprouvée plutôt que décrite."""
    from app.utils.pdf_theme import regle_page

    rendu = regle_page(taille="A6", marges="0", numeroter=False)
    assert "size: A6;" in rendu
    assert "margin: 0;" in rendu
    assert "counter(page)" not in rendu, (
        "une affiche d'une seule page ne porte pas « 1 / 1 »"
    )


def test_aucun_module_ne_REECRIT_la_regle_de_page():
    """🔴 La règle vit dans le thème, et nulle part ailleurs.

    Un `@page` anonyme écrit dans un document redéclare le format : c'est la
    forme exacte que ce lot vient de retirer de trois fichiers. Un quatrième
    document imprimable doit appeler `regle_page()`, pas recopier le bloc.
    """
    fautifs = {}
    for chemin in _fichiers():
        rel = chemin.relative_to(RACINE).as_posix()
        if rel == SOURCE:
            continue
        source = chemin.read_text(encoding="utf-8")
        #  Les lignes de PROSE citent la règle — on ne lit que le code.
        lignes = [
            n + 1
            for n, ligne in enumerate(source.split(chr(10)))
            if PAGE_ANONYME.search(ligne) and not ligne.lstrip().startswith(("#", "*"))
        ]
        if lignes:
            fautifs[rel] = lignes

    assert not fautifs, (
        f"Ces modules redéclarent le format d'une page imprimée : {fautifs}. "
        "Employer `pdf_theme.regle_page()` — A4 par défaut, et un format "
        "particulier se passe en argument, comme le fait l'annonce de hall."
    )


def test_cas_zero_le_motif_reconnait_bien_un_bloc_page():
    """Sans quoi le test ci-dessus serait vert sur n'importe quoi."""
    assert PAGE_ANONYME.search("@page { size: A4; }")
    assert PAGE_ANONYME.search("@page{size:A5}")
    #  Une page NOMMÉE n'est pas visée : elle ne porte pas le format.
    assert not PAGE_ANONYME.search("@page garde { margin: 0; }")
    assert len(_fichiers()) > 50, "le parcours ne décrit plus `app/`"


def test_les_trois_documents_passent_par_le_theme():
    """Le fait, pas la forme : chacun rend bien un bloc `@page` du thème.

    Un test qui ne chercherait que l'absence d'écriture locale resterait vert si
    un document cessait tout simplement de déclarer sa page — et hériterait alors
    du format du moteur, ce que ce lot existe pour empêcher.
    """
    from app.utils.annonce_hall import _css as css_annonce
    from app.utils.fiche_arrivant_css import CSS as CSS_FICHE
    from app.utils.manuel_pdf_css import css_du_pdf

    assert "size: A4;" in CSS_FICHE, "la fiche d'arrivant ne fixe plus son format"

    manuel = css_du_pdf("")
    assert "size: A4;" in manuel and "counter(page)" in manuel

    #  L'annonce de hall choisit son format selon le débordement : les trois
    #  gabarits doivent tous produire une page, et jamais un pied numéroté.
    for fmt, attendu in (("a4", "A4"), ("a5", "A5"), ("a6", "A6")):
        css = css_annonce(fmt)
        assert f"size: {attendu};" in css, (fmt, css[:80])
        assert "counter(page)" not in css
