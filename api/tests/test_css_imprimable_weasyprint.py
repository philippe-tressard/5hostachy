"""Les CSS imprimables n'emploient que ce que WeasyPrint sait lire.

## L'incident (11/09/2026)

Le filet doré à gauche du bandeau de périmètre a été refait en dégradé, pour
supprimer une double barre. Il s'affichait dans l'aperçu HTML — et **disparaissait
du PDF**, fond beige compris.

La cause, lue dans la source de WeasyPrint 69 (`css/tokens.py::parse_color_stop`) :

    if len(tokens) == 1:   ... couleur seule
    elif len(tokens) == 2: ... couleur + position
    raise InvalidValues

L'arrêt écrit était `var(--gold) 0 1.2mm` — **trois** jetons, la syntaxe CSS
Images Level 4 à deux positions. WeasyPrint lève, la déclaration `background`
entière est jetée, et **rien ne le dit** : pas d'erreur, pas de journal, un fond
simplement absent.

## 🔴 Ce que ce contrôle protège vraiment

**L'aperçu et le PDF ne sont pas rendus par le même moteur.** L'aperçu est du HTML
dans un navigateur ; le PDF sort de WeasyPrint. Une propriété que le navigateur
accepte et que WeasyPrint refuse produit deux résultats différents pour le même
code — et c'est l'aperçu, celui qu'on regarde, qui ment.

Le poste de développement ne peut pas rendre de PDF (bibliothèques natives
absentes sous Windows). Ce contrôle est donc le seul moyen d'attraper la classe
d'erreur ici, avant la production : il lit la règle **dans la source de
WeasyPrint** plutôt que de la recopier, et l'applique aux CSS qu'on écrit.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

#: Les modules qui composent une feuille de style destinée à WeasyPrint.
SOURCES = ("utils/annonce_hall.py", "utils/pdf_theme.py", "utils/fiche_arrivant.py")


def _regle_weasyprint() -> int:
    """Le nombre maximal de jetons qu'un arrêt de couleur admet, LU dans WeasyPrint.

    Le recopier ferait de ce test une seconde source de vérité : le jour où
    WeasyPrint accepterait la syntaxe à deux positions, ce contrôle continuerait
    de la refuser sans raison.
    """
    import importlib.util

    spec = importlib.util.find_spec("weasyprint")
    if spec is None or spec.origin is None:
        pytest.skip("WeasyPrint absent de cet environnement")
    tokens = Path(spec.origin).parent / "css" / "tokens.py"
    if not tokens.exists():
        pytest.skip("La source de WeasyPrint n'a pas la forme attendue")
    source = tokens.read_text(encoding="utf-8")
    corps = source[source.index("def parse_color_stop"):]
    corps = corps[: corps.index("\ndef ", 1)]
    longueurs = [int(n) for n in re.findall(r"len\(tokens\) == (\d+)", corps)]
    assert longueurs, "Cas zéro : `parse_color_stop` a changé de forme — contrôle inopérant."
    return max(longueurs)


def _arrets_de_couleur(css: str) -> list[tuple[str, str]]:
    """Les arrêts de chaque `linear-gradient(...)` trouvé, avec leur gradient."""
    arrets = []
    for gradient in re.findall(r"linear-gradient\(([^()]*(?:\([^()]*\)[^()]*)*)\)", css):
        morceaux = re.split(r",(?![^(]*\))", gradient)
        #  Le premier morceau est la DIRECTION (`to right`, `90deg`) quand il ne
        #  porte pas de couleur — il n'est pas un arrêt.
        for i, m in enumerate(morceaux):
            m = m.strip()
            if i == 0 and not re.search(r"#|var\(|rgb|[a-z]+\s*\d*%", m):
                continue
            if i == 0 and re.fullmatch(r"(to\s+\w+(\s+\w+)?|-?[\d.]+deg)", m):
                continue
            arrets.append((gradient.strip(), m))
    return arrets


def test_aucun_arret_de_couleur_ne_depasse_ce_que_weasyprint_lit():
    maxi = _regle_weasyprint()
    fautes = []
    vus = 0
    for rel in SOURCES:
        f = APP / rel
        if not f.exists():
            continue
        for gradient, arret in _arrets_de_couleur(f.read_text(encoding="utf-8")):
            vus += 1
            #  `var(--x)` compte pour UN jeton, comme dans tinycss2.
            jetons = re.sub(r"var\([^)]*\)", "VAR", arret).split()
            if len(jetons) > maxi:
                fautes.append(f"{rel} — « {arret} » ({len(jetons)} jetons) dans « {gradient[:60]}… »")

    assert vus > 0, (
        "Cas zéro : aucun dégradé trouvé dans les feuilles imprimables — "
        "l'extraction est cassée, ou les CSS ont changé de place."
    )
    assert not fautes, (
        f"WeasyPrint n'accepte qu'un arrêt de {maxi} jetons au plus "
        "(`css/tokens.py::parse_color_stop`) ; au-delà il lève et jette la "
        "déclaration ENTIÈRE, en silence :\n  " + "\n  ".join(fautes) +
        "\n\n  L'aperçu HTML continuerait de l'afficher — c'est ce qui a fait "
        "disparaître le filet du bandeau de périmètre le 11/09/2026."
    )
