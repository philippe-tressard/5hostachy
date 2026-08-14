"""Thème commun des documents imprimables (fiche arrivant, annonces hall).

Centralise ce qui était jusqu'ici dupliqué dans `fiche_arrivant.py` : logo,
palette de la charte graphique, **icônes**, helpers data-URI et rendu HTML → PDF.

Tout nouveau document imprimable passe par ce module — ne pas redéfinir de
palette, de logo ni de moteur PDF ailleurs. Cette consigne existait déjà et
n'était pas tenue : `utils/email/gabarit.py` redessinait le logo (14/08/2026).
Elle vaut aussi pour ce qui n'est pas un PDF — un e-mail affiche la même marque.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import mimetypes
from pathlib import Path

logger = logging.getLogger("hostachy.pdf_theme")

# Racine des fichiers uploadés dans le conteneur API (volume Docker `uploads`).
UPLOADS_ROOT = Path("/app")


# ── Palette (specs/design/charte-graphique.md) ───────────────────────────────

PALETTE_CSS = """\
:root {
  --navy: #1E3A5F; --navy-dark: #16304F; --gold: #C9983A; --green: #3D6B4F;
  --bg: #F2EFE9; --card: #FFFFFF; --ink: #1A1A2E; --muted: #5A6070;
  --light-muted: #8A8FA0; --footer-bg: #FAFAF7; --border: #E5E2DC;
}
"""

FONT_SERIF = "Georgia, 'Palatino Linotype', 'Book Antiqua', Palatino, serif"
FONT_SANS = (
    "'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, "
    "'Helvetica Neue', Arial, sans-serif"
)


# ── Logo ─────────────────────────────────────────────────────────────────────

def logo_svg(size: int = 36) -> str:
    """Logo 5Hostachy en SVG inline (immeuble + vague de Seine)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        f'width="{size}" height="{size}">\n'
        '  <rect width="64" height="64" rx="14" fill="#1E3A5F"/>\n'
        '  <g fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" '
        'stroke-linejoin="round">\n'
        '    <path d="M18 54V18a4 4 0 0 1 4-4h20a4 4 0 0 1 4 4v36Z"/>\n'
        '    <path d="M18 34h-6a4 4 0 0 0-4 4v16h10"/>\n'
        '    <path d="M46 30h6a4 4 0 0 1 4 4v20H46"/>\n'
        '    <path d="M25 22h14"/><path d="M25 30h14"/><path d="M25 38h14"/>'
        '<path d="M25 46h14"/>\n'
        '  </g>\n'
        '  <path d="M48 50c0 4.4-3.6 8-8 8h14a8 8 0 0 0-6-8Z" fill="#C9983A" opacity=".95"/>\n'
        '</svg>'
    )


# ── Icônes ───────────────────────────────────────────────────────────────────

#: Catalogue des tracés, **copie octet pour octet** de `front/src/lib/icones-svg.json`.
#:
#: Pourquoi une copie et non un fichier unique : les contextes de build Docker
#: sont `./api` et `./front` (docker-compose.yml). Un fichier posé à la racine du
#: dépôt n'entre dans **aucune** des deux images — « une source lue des deux
#: côtés » supposerait d'élargir les deux contextes, donc de toucher la chaîne de
#: déploiement des deux RPi pour un sujet d'affichage.
#:
#: Ce qui rend la copie sûre, c'est `api/tests/test_icones_svg.py` : il échoue si
#: les deux fichiers diffèrent d'un octet, et si un tracé réapparaît en dur d'un
#: côté ou de l'autre. Sans lui, ce serait la duplication interdite par
#: `standards/02-factorisation.md` ; avec lui, c'est un artefact dérivé dont la
#: divergence est impossible. Même pattern que `docs/manuel-utilisateur.html` →
#: `front/static/`.
_CATALOGUE_ICONES = Path(__file__).with_name("icones-svg.json")

_icones_cache: dict[str, str] | None = None


def _icones() -> dict[str, str]:
    global _icones_cache
    if _icones_cache is None:
        try:
            _icones_cache = json.loads(_CATALOGUE_ICONES.read_text(encoding="utf-8"))
        except Exception as exc:
            #  Un document sans ses icônes reste lisible ; un document qui ne se
            #  génère pas ne l'est pas. On journalise et on continue sans.
            logger.error("Catalogue d'icônes illisible (%s) — documents rendus sans icône", exc)
            _icones_cache = {}
    return _icones_cache


def icone_svg(
    nom: str | None,
    *,
    taille: int = 14,
    couleur: str = "#1E3A5F",
    style_sup: str = "vertical-align:-2px;margin-right:3px",
) -> str:
    """Une icône du catalogue en SVG inline, prête pour WeasyPrint.

    Renvoie une **chaîne vide** si le nom est absent ou inconnu : un périmètre
    sans icône est un état normal (le champ `icone` est facultatif), il ne doit
    produire ni carré vide ni point d'interrogation. C'est pourquoi il n'y a pas
    ici le repli `help-circle` du composant `Icon.svelte` — à l'écran, une icône
    manquante signale une erreur de saisie ; sur un document imprimé, elle
    n'apporterait qu'un pictogramme incompréhensible à côté d'un nom de bâtiment.

    `stroke` **et** `color` portent la couleur explicitement : WeasyPrint n'hérite
    pas `currentColor` de façon fiable, et deux tracés du catalogue s'en servent
    pour leur remplissage.
    """
    trace = _icones().get((nom or "").strip())
    if not trace:
        return ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'width="{taille}" height="{taille}" fill="none" stroke="{couleur}" '
        f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'style="color:{couleur};{style_sup}">{trace}</svg>'
    )


# ── Data-URI ─────────────────────────────────────────────────────────────────

def qr_data_uri(url: str) -> str:
    """QR code → `data:image/png;base64,…` (chaîne vide si génération impossible)."""
    if not url:
        return ""
    try:
        import qrcode

        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        return ""


def image_data_uri(image_url: str | None) -> str | None:
    """Image locale (`/uploads/…`) → data-URI, ou None si absente/illisible.

    Les documents sont générés hors requête HTTP (BackgroundTask) : les
    ressources doivent être embarquées, jamais référencées par URL.
    """
    if not image_url:
        return None
    path = UPLOADS_ROOT / image_url.lstrip("/")
    if not path.is_file():
        return None
    try:
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"
    except Exception:
        return None


# ── Rendu PDF ────────────────────────────────────────────────────────────────

def html_to_pdf(html: str) -> bytes:
    """Rend un document HTML autonome en PDF (WeasyPrint).

    Le HTML doit être **autonome** : CSS inline dans une balise `<style>` et
    images en data-URI (cf. `image_data_uri` / `qr_data_uri`). Aucune requête
    réseau n'est effectuée au rendu.
    """
    from weasyprint import HTML  # import différé : lib lourde, chargée à l'usage

    return HTML(string=html).write_pdf()
