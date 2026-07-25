"""Génération des annonces affichées dans le hall des bâtiments (A4 / A5).

Le rendu réutilise le thème imprimable commun (`pdf_theme`) : même palette,
même logo et même moteur PDF que la fiche arrivant.

Format : A5 pour un message court, A4 au-delà (cf. `choisir_format`). Le CS peut
forcer l'un ou l'autre depuis l'interface.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from html import escape

from app.utils.pdf_theme import (
    FONT_SANS,
    FONT_SERIF,
    PALETTE_CSS,
    html_to_pdf,
    image_data_uri,
    logo_svg,
    qr_data_uri,
)

# Au-delà de ce nombre de caractères (texte brut), l'annonce passe en A4.
# Formats retenus, du plus grand au plus petit.
FORMATS = ("a4", "a5", "a6", "a7", "a8")

# Photos facultatives, placées en pied de contenu. Volontairement limité : au-delà,
# l'affiche déborderait du feuillet et le format ne serait plus tenu.
MAX_PHOTOS = 2

# En dessous de l'A5, une affiche avec photo devient illisible : on ne descend pas.
FORMAT_MIN_AVEC_PHOTOS = "a5"

# Poids maximal du contenu (titre + message, en caractères) tenant dans chaque
# format. Au-delà du dernier seuil, on reste en A4.
SEUILS_FORMAT: tuple[tuple[str, int], ...] = (
    ("a8", 70),
    ("a7", 140),
    ("a6", 300),
    ("a5", 600),
)

# Gabarit par format : dimensions de page et échelle typographique.
_GABARITS: dict[str, dict[str, str]] = {
    "a4": {
        "page_size": "A4",
        "largeur": "210mm",
        "hauteur": "297mm",
        "padding": "14mm 16mm",
        "logo": "44",
        "surtitre": "10pt",
        "residence": "13pt",
        "titre": "30pt",
        "meta": "10pt",
        "corps": "13pt",
        "galerie_max": "44mm",
        "qr": "26mm",
        "pied": "9pt",
    },
    "a5": {
        "page_size": "A5",
        "largeur": "148mm",
        "hauteur": "210mm",
        "padding": "10mm 12mm",
        "logo": "32",
        "surtitre": "8pt",
        "residence": "10.5pt",
        "titre": "21pt",
        "meta": "8.5pt",
        "corps": "10.5pt",
        "galerie_max": "30mm",
        "qr": "19mm",
        "pied": "7.5pt",
    },
    "a6": {
        "page_size": "A6",
        "largeur": "105mm",
        "hauteur": "148mm",
        "padding": "7mm 8mm",
        "logo": "24",
        "surtitre": "6.5pt",
        "residence": "8.5pt",
        "titre": "15pt",
        "meta": "7pt",
        "corps": "8.5pt",
        "galerie_max": "0mm",   # pas de photo en dessous de l'A5
        "qr": "13mm",
        "pied": "6pt",
    },
    "a7": {
        "page_size": "A7",
        "largeur": "74mm",
        "hauteur": "105mm",
        "padding": "5mm 5.5mm",
        "logo": "17",
        "surtitre": "5pt",
        "residence": "6.5pt",
        "titre": "11pt",
        "meta": "5.5pt",
        "corps": "7pt",
        "galerie_max": "0mm",
        "qr": "0mm",            # pied simplifié : plus de QR
        "pied": "5pt",
    },
    "a8": {
        "page_size": "A8",
        "largeur": "52mm",
        "hauteur": "74mm",
        "padding": "3.5mm 4mm",
        "logo": "13",
        "surtitre": "4pt",
        "residence": "5.5pt",
        "titre": "8.5pt",
        "meta": "4.5pt",
        "corps": "6pt",
        "galerie_max": "0mm",
        "qr": "0mm",
        "pied": "4.5pt",
    },
}

# Formats trop petits pour porter le QR code du pied de page.
_SANS_QR = ("a7", "a8")

_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)

# Balises et attributs retirés avant rendu — défense en profondeur côté serveur,
# en complément du `safeHtml()` appliqué à l'affichage côté front.
_BALISES_INTERDITES = re.compile(
    r"<\s*(script|style|iframe|object|embed|link|meta)\b.*?(?:</\s*\1\s*>|>)",
    re.IGNORECASE | re.DOTALL,
)
_ATTRS_INTERDITS = re.compile(r"\s(on\w+|srcdoc)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)


# ── Helpers ──────────────────────────────────────────────────────────────────

def texte_brut(html: str) -> str:
    """HTML riche → texte brut (pendant serveur de `stripHtml` côté front)."""
    txt = re.sub(r"<[^>]*>", " ", html or "")
    txt = (
        txt.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
        .replace("&gt;", ">").replace("&quot;", '"')
    )
    return re.sub(r"\s+", " ", txt).strip()


def nettoyer_html(html: str) -> str:
    """Retire les balises et attributs exécutables du message saisi."""
    return _ATTRS_INTERDITS.sub("", _BALISES_INTERDITES.sub("", html or ""))


def choisir_format(
    message_html: str,
    format_demande: str = "auto",
    *,
    titre: str = "",
    avec_photos: bool = False,
) -> str:
    """Retourne le format effectif (`a4` … `a8`).

    En mode `auto`, on retient **le plus petit format** qui accueille le
    contenu : une annonce courte occupe ainsi moins de place dans l'afficheur
    du hall. Un choix explicite du CS est prioritaire.

    Une affiche portant des photos ne descend jamais sous
    `FORMAT_MIN_AVEC_PHOTOS` : en dessous, la photo écrase le texte.
    """
    demande = (format_demande or "auto").lower()
    if demande in FORMATS:
        return demande

    poids = len(texte_brut(message_html)) + len(texte_brut(titre))
    format_retenu = "a4"
    for fmt, seuil in SEUILS_FORMAT:
        if poids <= seuil:
            format_retenu = fmt
            break

    if avec_photos and FORMATS.index(format_retenu) > FORMATS.index(FORMAT_MIN_AVEC_PHOTOS):
        return FORMAT_MIN_AVEC_PHOTOS
    return format_retenu


def format_libelle(fmt: str) -> str:
    return (fmt or "a4").upper()


def perimetre_libelle(perimetres: list[str], batiments: dict[int, str] | None = None) -> str:
    """`['bat:1','parking']` → `Bât. 1 · Parking` (séparateur ` · ` de la charte)."""
    if not perimetres or perimetres == ["résidence"]:
        return "Copropriété entière"
    noms = batiments or {}
    libelles: list[str] = []
    for p in perimetres:
        if p == "résidence":
            libelles.append("Copropriété entière")
        elif p.startswith("bat:"):
            ident = p.split(":", 1)[1]
            libelles.append(f"Bât. {noms.get(int(ident), ident)}" if ident.isdigit() else f"Bât. {ident}")
        elif p == "parking":
            libelles.append("Parking")
        elif p == "cave":
            libelles.append("Cave")
        elif p == "aful":
            libelles.append("AFUL")
        else:
            libelles.append(p)
    return " · ".join(libelles)


def date_longue(d: date | datetime) -> str:
    """`date(2026, 7, 25)` → `25 juillet 2026`."""
    return f"{d.day} {_MOIS[d.month - 1]} {d.year}"


def nom_fichier(titre: str, cree_le: date | datetime) -> str:
    """Nom de fichier proposé au téléchargement / en pièce jointe.

    Les accents sont translittérés (`août` → `aout`) : le nom traverse SMTP et
    des systèmes de fichiers variés, on le garde en ASCII.
    """
    sans_accent = unicodedata.normalize("NFKD", texte_brut(titre))
    sans_accent = sans_accent.encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", sans_accent).strip("-").lower()[:60]
    return f"annonce-{cree_le:%Y%m%d}-{slug or 'hall'}.pdf"


# ── CSS ──────────────────────────────────────────────────────────────────────

def _css(fmt: str) -> str:
    g = _GABARITS[fmt]
    # Sous l'A4, la feuille imprimée est plus grande que l'affiche : on matérialise
    # le trait de coupe.
    coupe = (
        "border: .35mm dashed var(--light-muted);" if fmt != "a4" else ""
    )
    # Très petits formats : on sacrifie la date d'affichage pour préserver le texte.
    meta_allegee = ".date-affichage { display: none; }" if fmt in _SANS_QR else ""
    return f"""\
@page {{ size: {g['page_size']}; margin: 0; }}
{PALETTE_CSS}\
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: {FONT_SANS};
  color: var(--ink); background: var(--card); line-height: 1.5;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}}
/* Dimensions physiques du feuillet : le pied de page se cale au bas du {g['page_size']},
   à l'impression comme à l'aperçu écran (où @page n'est pas appliqué). */
.page {{
  width: {g['largeur']}; min-height: {g['hauteur']};
  margin: 0 auto; background: var(--card);
  display: flex; flex-direction: column;
  {coupe}
}}
/* Aperçu écran uniquement — WeasyPrint rend en média « print » et ignore ce bloc. */
@media screen {{
  body {{ background: #DCD8D0; padding: 6mm 0; }}
  .page {{ box-shadow: 0 2mm 6mm rgba(30, 58, 95, .22); }}
}}

/* ── En-tête ── */
.entete {{
  background: linear-gradient(135deg, var(--navy) 0%, var(--navy-dark) 100%);
  padding: {g['padding']}; padding-top: 8mm; padding-bottom: 7mm;
  display: flex; align-items: center; gap: 5mm;
}}
.entete svg {{ flex-shrink: 0; }}
.entete-texte {{ flex: 1; }}
.surtitre {{
  font-size: {g['surtitre']}; color: var(--gold); font-weight: 700;
  letter-spacing: 2.2px; text-transform: uppercase;
}}
.residence {{
  font-family: {FONT_SERIF}; font-size: {g['residence']};
  font-weight: 700; color: #FFFFFF; margin-top: 1mm;
}}
.barre-accent {{
  height: 2.2mm;
  background: linear-gradient(90deg, var(--gold) 0%, var(--navy) 50%, var(--green) 100%);
}}

/* ── Corps ── */
.corps {{ flex: 1; padding: {g['padding']}; display: flex; flex-direction: column; }}
.meta {{
  display: flex; align-items: center; justify-content: space-between;
  gap: 4mm; margin-bottom: 5mm;
}}
.chip-perimetre {{
  font-size: {g['meta']}; font-weight: 700; color: var(--navy);
  background: #F0EDE6; border-left: 1.2mm solid var(--gold);
  padding: 1.6mm 3.5mm; border-radius: 1mm;
  text-transform: uppercase; letter-spacing: .6px;
}}
.date-affichage {{ font-size: {g['meta']}; color: var(--muted); white-space: nowrap; }}
{meta_allegee}
.titre {{
  font-family: {FONT_SERIF}; font-size: {g['titre']}; font-weight: 700;
  color: var(--navy); line-height: 1.15; margin-bottom: 4mm;
}}
.filet {{ height: .4mm; background: var(--border); margin-bottom: 5mm; }}
.message {{ font-size: {g['corps']}; color: var(--ink); }}
.message p {{ margin-bottom: 2.5mm; }}
.message ul, .message ol {{ margin: 0 0 2.5mm 6mm; }}
.message li {{ margin-bottom: 1.2mm; }}
.message strong {{ color: var(--navy); }}
.message h1, .message h2, .message h3 {{
  font-family: {FONT_SERIF}; color: var(--navy);
  margin: 3mm 0 2mm; line-height: 1.2;
}}
.message a {{ color: var(--navy); text-decoration: underline; }}
.message img {{ max-width: 100%; border-radius: 1.5mm; }}

/* ── Photos : secondaires, calées en pied de contenu (le texte reste central) ── */
.galerie {{ display: flex; gap: 3mm; margin-top: auto; padding-top: 6mm; }}
.galerie img {{
  flex: 1 1 0; min-width: 0; height: {g['galerie_max']};
  object-fit: cover; border-radius: 2mm; border: .3mm solid var(--border);
}}

/* ── Pied de page ── */
.pied {{
  background: var(--footer-bg); border-top: .3mm solid var(--border);
  padding: {g['padding']}; padding-top: 5mm; padding-bottom: 5mm;
  display: flex; align-items: center; gap: 5mm;
}}
.pied-texte {{ flex: 1; font-size: {g['pied']}; color: var(--muted); line-height: 1.45; }}
.pied-signature {{ font-weight: 700; color: var(--navy); }}
.pied-site {{ color: var(--navy); font-weight: 600; }}
.pied-qr {{ width: {g['qr']}; height: {g['qr']}; flex-shrink: 0; }}
"""


# ── Rendu ────────────────────────────────────────────────────────────────────

def construire_html(
    *,
    titre: str,
    message_html: str,
    perimetre_label: str,
    format_effectif: str,
    site_nom: str,
    site_url: str,
    images: list[str] | None = None,
    date_affichage: date | datetime | None = None,
) -> str:
    """Assemble le HTML autonome de l'annonce (images et QR en data-URI)."""
    g = _GABARITS[format_effectif]
    d = date_affichage or datetime.utcnow()
    url_complete = site_url if site_url.startswith("http") else f"https://{site_url}"
    site_affiche = re.sub(r"^https?://", "", site_url).rstrip("/")

    alt = escape(titre)

    # Photos facultatives, embarquées comme le reste (data-URI).
    # Ignorées sous l'A5 : le gabarit n'a pas la place de les porter.
    galerie = ""
    photos_admises = (
        (images or [])[:MAX_PHOTOS]
        if FORMATS.index(format_effectif) <= FORMATS.index(FORMAT_MIN_AVEC_PHOTOS)
        else []
    )
    vignettes = [uri for uri in (image_data_uri(u) for u in photos_admises) if uri]
    if vignettes:
        balises = "".join(f'<img src="{uri}" alt="{alt}">' for uri in vignettes)
        galerie = f'<div class="galerie">{balises}</div>'

    qr = "" if format_effectif in _SANS_QR else qr_data_uri(url_complete)
    qr_html = f'<img class="pied-qr" src="{qr}" alt="QR {escape(site_affiche)}">' if qr else ""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{escape(titre)} — {escape(site_nom)}</title>
<style>
{_css(format_effectif)}
</style>
</head>
<body>
<div class="page">

  <div class="entete">
    {logo_svg(int(g['logo']))}
    <div class="entete-texte">
      <div class="surtitre">Avis aux résidents</div>
      <div class="residence">{escape(site_nom)}</div>
    </div>
  </div>
  <div class="barre-accent"></div>

  <div class="corps">
    <div class="meta">
      <span class="chip-perimetre">{escape(perimetre_label)}</span>
      <span class="date-affichage">Affiché le {date_longue(d)}</span>
    </div>
    <h1 class="titre">{escape(titre)}</h1>
    <div class="filet"></div>
    <div class="message">{nettoyer_html(message_html)}</div>
    {galerie}
  </div>

  <div class="pied">
    <div class="pied-texte">
      <span class="pied-signature">Le Conseil Syndical</span> — {escape(site_nom)}<br>
      Retrouvez toutes les informations de la résidence sur
      <span class="pied-site">{escape(site_affiche)}</span>
    </div>
    {qr_html}
  </div>

</div>
</body>
</html>"""


def generer_pdf(**kwargs) -> bytes:
    """Construit le HTML de l'annonce puis le rend en PDF."""
    return html_to_pdf(construire_html(**kwargs))
