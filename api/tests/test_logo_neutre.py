"""Le logo neutre : UN dessin, et tout ce qui le montre en dérive (#1728).

Il existe sous cinq formes, parce que chaque lieu prend son format : le SVG du
front (`favicon.svg`), sa copie dans l'API (les documents imprimés, par
`pdf_theme.logo_svg`), et trois rendus PNG — celui de l'API (courriels, route
publique `GET /config/logo.png`) et les deux icônes de l'application installée.

Rien ne les tenait ensemble : `pdf_theme.logo_svg` recopiait le dessin en
chaîne Python, et changer le logo neutre demandait de penser aux quatre
autres. Ce contrôle refuse qu'ils divergent.

Les PNG ne se rendent pas en CI (aucun moteur SVG n'y est installé) : on vérifie
qu'ils SONT le rendu du dessin en lisant leurs pixels aux endroits que le dessin
définit. Pour les refaire après avoir changé le SVG, le rendre à 512 et 192 px
sur fond transparent (un navigateur suffit : Playwright, `omitBackground`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.utils import logo, pdf_theme

RACINE = Path(__file__).resolve().parents[2]
SVG_FRONT = RACINE / "front" / "static" / "favicon.svg"
ICONES = RACINE / "front" / "static" / "icons"

BLEU, OR, BLANC = (0x1E, 0x3A, 0x5F), (0xC9, 0x98, 0x3A), (0xFF, 0xFF, 0xFF)

#: Des points du dessin, dans le repère du SVG (512 px) AVANT sa mise à l'échelle
#: dans la tuile (`translate(256 256) scale(0.8) translate(-256 -296.25)`), et la
#: couleur qu'ils doivent avoir. Un point par élément qui fait le logo.
POINTS = (
    ((292.5, 177.0), OR, "la fenêtre allumée"),
    ((137.5, 350.0), BLEU, "le mur gauche de la tour"),
    ((219.5, 244.0), BLEU, "une fenêtre éteinte"),
    ((256.0, 487.5), OR, "la ligne de sol"),
    ((256.0, 440.0), BLANC, "l'intérieur de la tour"),
)


def _exige(chemin: Path) -> Path:
    """Jamais `skip` : un fichier disparu doit faire rougir la CI (`standards/04`)."""
    if not chemin.is_file():
        pytest.fail(f"Fichier attendu introuvable : {chemin.relative_to(RACINE)}")
    return chemin


def _dans_la_tuile(x: float, y: float, cote: int) -> tuple[int, int]:
    echelle = cote / 512
    return round((256 + 0.8 * (x - 256)) * echelle), round((256 + 0.8 * (y - 296.25)) * echelle)


def _proche(pixel: tuple, couleur: tuple) -> bool:
    return pixel[3] > 250 and sum(abs(pixel[i] - couleur[i]) for i in range(3)) < 40


def test_l_api_porte_la_copie_exacte_du_dessin_du_front():
    assert _exige(pdf_theme.LOGO_NEUTRE_SVG).read_bytes() == _exige(SVG_FRONT).read_bytes(), (
        "logo-neutre.svg (API) et favicon.svg (front) divergent : recopier le second sur le premier"
    )


def test_le_png_de_l_api_est_l_icone_512_du_front():
    assert _exige(logo.NEUTRE_PNG).read_bytes() == _exige(ICONES / "icon-512.png").read_bytes()


@pytest.mark.parametrize("nom, cote", [("icon-512.png", 512), ("icon-192.png", 192)])
def test_chaque_png_est_le_rendu_du_dessin(nom, cote):
    image = Image.open(_exige(ICONES / nom)).convert("RGBA")
    assert image.size == (cote, cote)
    for (x, y), couleur, quoi in POINTS:
        pixel = image.getpixel(_dans_la_tuile(x, y, cote))
        assert _proche(pixel, couleur), f"{nom} : {quoi} vaut {pixel}, attendu {couleur}"
    #  La tuile est arrondie : son coin reste transparent, son bord est blanc.
    assert image.getpixel((1, 1))[3] == 0, f"{nom} : le coin de la tuile n'est pas transparent"
    assert _proche(image.getpixel((cote // 2, 2)), BLANC), f"{nom} : la tuile n'est pas blanche"


def test_les_documents_recoivent_le_dessin_a_leur_taille_sans_son_commentaire():
    svg = pdf_theme.logo_svg(48)
    assert svg.startswith('<svg width="48" height="48" ')
    assert "<!--" not in svg, "la provenance du dessin partait dans chaque document"
    assert 'fill="#C9983A"' in svg
