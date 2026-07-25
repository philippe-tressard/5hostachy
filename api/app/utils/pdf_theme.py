"""Thème commun des documents imprimables (fiche arrivant, annonces hall).

Centralise ce qui était jusqu'ici dupliqué dans `fiche_arrivant.py` : logo,
palette de la charte graphique, helpers data-URI et rendu HTML → PDF.

Tout nouveau document imprimable passe par ce module — ne pas redéfinir de
palette, de logo ni de moteur PDF ailleurs.
"""
from __future__ import annotations

import base64
import io
import mimetypes
from pathlib import Path

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
