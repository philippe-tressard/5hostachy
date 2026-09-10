"""L'affiche de hall ne peint jamais deux fois le même fond.

## L'incident (11/09/2026) — la TROISIÈME fois

« Le PDF généré dans l'affiche comprend deux barres orange à gauche du périmètre,
alors que l'aperçu n'en contient qu'une. »

Les deux correctifs précédents (18/08, puis 10/09) ont cherché le défaut dans le
**dessin** du filet : d'abord son rayon, puis sa bordure, enfin remplacée par un
dégradé pour n'avoir « qu'une seule surface peinte ». Le raisonnement était juste
et la cause était ailleurs — le filet est peint une fois, c'est **le fond entier**
qui l'est deux fois.

`.meta` est un conteneur flex ; le bandeau de périmètre est un `<span>`, donc une
boîte inline. WeasyPrint 69 emballe un enfant inline de conteneur flex dans un
bloc anonyme **qui hérite du style de l'élément, fond compris**, puis peint le
dégradé sur les deux : une fois sur l'emballage étiré à la largeur de la ligne
flex, une fois sur la boîte inline ajustée au texte. Deux origines, deux filets.

Le navigateur, lui, n'a pas d'emballage à créer : l'aperçu montrait donc un seul
filet. Encore un écart entre les deux moteurs — la même famille que
`test_css_imprimable_weasyprint.py`.

## Pourquoi ce contrôle-ci, et pas une relecture du CSS

Trois correctifs, trois fois la même certitude d'avoir traité la cause. Lire la
feuille de style n'a jamais suffi, parce que le défaut ne s'y voit pas : il naît
de la **mise en page**, pas de la déclaration. Ce contrôle rend donc l'affiche et
regarde ce qui est réellement peint dans le flux de contenu du PDF — le fait,
pas le symptôme attendu.

Il attrape la classe entière : n'importe quel élément inline à fond peint placé
dans un conteneur flex se signalera de la même façon, quel que soit son nom.

## Ce qu'il ne peut pas vérifier

Le poste de développement n'a pas les bibliothèques natives de WeasyPrint (elles
sont dans `api/Dockerfile`) : le contrôle y renvoie INCONNU (`skip`), jamais OK.
La CI, elle, installe pango/cairo — c'est là qu'il fait barrage.
"""
from __future__ import annotations

import re
import zlib

import pytest

from app.utils.annonce_hall import FORMATS, construire_html

#: Un remplissage de motif dans le flux de contenu : `/pN scn` puis `x y l h re f`.
_APLAT = re.compile(r"/p\d+ scn\s+([\d.-]+) ([\d.-]+) ([\d.-]+) ([\d.-]+) re")

_ARGUMENTS = dict(
    titre="Rénovation complète de l’ascenseur du bâtiment 1 du 28/9 au 16/10",
    message_html="<p>La société Koné informe le Conseil syndical que les travaux "
    "commenceront le lundi 28 septembre.</p>",
    perimetre_label="Bât. 1 › Ascenseur",
    site_nom="5Hostachy",
    site_url="5hostachy.fr",
)


def _flux_de_contenu(html: str) -> str:
    """Le PDF rendu, ramené à son texte lisible (flux décompressés)."""
    weasyprint = pytest.importorskip(
        "weasyprint", reason="WeasyPrint ne peut pas RENDRE ici (pango/cairo absents)"
    )
    pdf = weasyprint.HTML(string=html).write_pdf()
    morceaux = [pdf.decode("latin-1")]
    for brut in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            morceaux.append(zlib.decompress(brut).decode("latin-1"))
        except zlib.error:
            continue
    return "\n".join(morceaux)


def _aplats(html: str) -> list[tuple[float, float, float, float]]:
    """Les rectangles peints avec un dégradé, en (gauche, haut, droite, bas)."""
    trouves = []
    for x, y, largeur, hauteur in _APLAT.findall(_flux_de_contenu(html)):
        x, y, largeur, hauteur = float(x), float(y), float(largeur), float(hauteur)
        trouves.append((x, y, x + largeur, y + hauteur))
    return trouves


def _se_recouvrent(a, b) -> bool:
    """Deux rectangles partagent-ils une surface ? (se toucher ne compte pas)"""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@pytest.mark.parametrize("format_effectif", FORMATS)
def test_aucun_degrade_n_est_peint_deux_fois(format_effectif: str):
    html = construire_html(format_effectif=format_effectif, **_ARGUMENTS)
    aplats = _aplats(html)

    #  Cas zéro : l'affiche porte trois dégradés — l'en-tête, la barre d'accent
    #  et le bandeau de périmètre. N'en trouver aucun voudrait dire que
    #  l'extraction est cassée, pas que le document est sain.
    assert len(aplats) >= 3, (
        f"Cas zéro : {len(aplats)} aplat(s) de dégradé trouvé(s) dans le PDF {format_effectif} "
        "au lieu des trois attendus — le flux de contenu a changé de forme, ce "
        "contrôle ne mesure plus rien."
    )

    doublons = [
        (a, b)
        for i, a in enumerate(aplats)
        for b in aplats[i + 1:]
        if _se_recouvrent(a, b)
    ]
    assert not doublons, (
        f"Deux dégradés se recouvrent dans l'affiche {format_effectif} :\n  "
        + "\n  ".join(f"{a} recouvre {b}" for a, b in doublons)
        + "\n\n  Signature du fond peint DEUX fois : WeasyPrint emballe un enfant "
        "inline de conteneur flex dans un bloc anonyme qui hérite de son fond, "
        "et peint les deux. C'est ce qui a mis deux filets dorés à gauche du "
        "bandeau de périmètre, alors que l'aperçu HTML n'en montrait qu'un.\n"
        "  Correctif : donner à l'élément un `display` de niveau bloc "
        "(`inline-block` suffit) — un bloc n'a pas d'emballage à recevoir."
    )
