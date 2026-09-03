"""Le manuel utilisateur en PDF — page de garde, sommaire, mentions.

## 🔴 UNE SEULE SOURCE, ET C'EST LE POINT QUI COMPTE

Le PDF n'est **pas une seconde rédaction** du manuel : il en est une mise en
page. Le contenu est lu tel qu'il est servi aux résidents —
`http://front:3000/manuel-utilisateur.html`, le conteneur voisin — puis
transformé.

Écrire un second document aurait été plus simple à court terme et faux à moyen
terme : ce dépôt a déjà payé quatre fois la divergence de deux textes qui
décrivent la même chose (périmètres, canaux de notification, table des pages,
chiffres du manuel). Un PDF re-rédigé aurait divergé au premier écran modifié,
sans que rien ne le signale — et c'est le PDF, imprimé et distribué, qu'on aurait
lu le plus longtemps après sa péremption.

⚠️ **Cette lecture est une requête réseau, et c'est assumé.** La règle du dépôt —
« aucune requête au rendu » — vise les RESSOURCES (images, polices, CSS), qui
doivent être embarquées en data-URI parce qu'elles sont chargées hors requête
HTTP. Ici on récupère la SOURCE, une fois, avant de composer. Si le front est
indisponible, la génération échoue franchement : mieux vaut pas de PDF qu'un PDF
d'un manuel qu'on n'a pas pu lire.

## Ce que la mise en page ajoute

| | |
|---|---|
| **page de garde** | logo, titre, le QR code du site, la date d'édition |
| **sommaire** | construit depuis les `<h2>` réellement présents — jamais une liste tenue à la main |
| **mentions** | éditeur, version du manuel, avertissement de péremption |

Le sommaire mérite un mot : le construire **depuis le document** est ce qui
l'empêche de mentir. Une table des matières recopiée est une table de plus, et ce
manuel vient précisément de perdre toutes ses tables recopiées (#651).
"""
from __future__ import annotations

import re
import urllib.request
from datetime import date
from html import escape, unescape

from app.utils.dates_fr import date_longue
from app.utils.pdf_theme import (
    FONT_SANS,
    FONT_SERIF,
    PALETTE_CSS,
    html_to_pdf,
    logo_svg,
    qr_data_uri,
)

#: Le manuel, tel qu'il est SERVI. Nom de service Docker : les deux conteneurs
#: partagent le réseau `hostachy`.
URL_MANUEL_INTERNE = "http://front:3000/manuel-utilisateur.html"

#: Ce qu'on garde du manuel : son corps, sans la barre latérale ni le script de
#: navigation, qui n'ont aucun sens sur un feuillet imprimé.
_MAIN = re.compile(r"<main[^>]*>(.*?)</main>", re.S | re.I)
_TITRES = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S | re.I)
_BALISES = re.compile(r"<[^>]+>")
_VERSION = re.compile(r"Manuel utilisateur (v[\d.]+)")


class ManuelIndisponible(RuntimeError):
    """Le manuel n'a pas pu être lu — on ne compose pas un PDF sur du vide."""


def lire_manuel(url: str = URL_MANUEL_INTERNE, timeout: float = 5.0) -> str:
    """Le manuel tel qu'il est servi aux résidents.

    Lève `ManuelIndisponible` plutôt que de rendre une chaîne vide : un PDF d'un
    manuel qu'on n'a pas pu lire serait une couverture et rien d'autre, et
    personne ne s'en apercevrait avant de l'ouvrir.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as reponse:  # noqa: S310
            if reponse.status != 200:
                raise ManuelIndisponible(f"HTTP {reponse.status} sur {url}")
            brut = reponse.read()
    except ManuelIndisponible:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ManuelIndisponible(f"manuel illisible ({url}) : {exc}") from exc

    texte = brut.decode("utf-8", "replace")
    if "ecran-card" not in texte:
        raise ManuelIndisponible(
            "le document lu n'est pas le manuel : sa grille des écrans est absente"
        )
    return texte


def corps_du_manuel(html: str) -> str:
    """Le contenu imprimable : le `<main>`, sans la navigation ni les scripts.

    🔴 LES BLOCS DÉPLIABLES SONT OUVERTS À LA COMPOSITION, pas par du CSS.

    Un `<details>` fermé est du contenu **invisible** — donc, sur du papier, du
    contenu perdu. Et c'est justement celui qu'on a demandé à voir : Tickets,
    Communauté et Mon profil, les trois écrans dont l'usage ne se devine pas.

    La première version s'en remettait à `display: block !important` sur l'enfant.
    Ça ne suffit pas : le repli d'un `<details>` est un comportement natif, pas
    une règle de style — le navigateur l'a confirmé à l'aperçu, et un moteur PDF
    n'a aucune raison de faire mieux. On transforme donc la balise, ce qui ne
    dépend d'aucun moteur.

    Le `<summary>` devient un intertitre : « En savoir plus » n'a plus de sens
    quand tout est déjà là, mais le supprimer collerait deux paragraphes.
    """
    trouve = _MAIN.search(html)
    corps = trouve.group(1) if trouve else html
    corps = re.sub(r"<script.*?</script>", "", corps, flags=re.S | re.I)
    corps = re.sub(
        r"<summary[^>]*>.*?</summary>",
        '<p class="ecran-detail-titre">En détail</p>',
        corps,
        flags=re.S | re.I,
    )
    corps = re.sub(r"<details([^>]*)>", r"<div>", corps, flags=re.I)
    corps = re.sub(r"</details>", "</div>", corps, flags=re.I)
    #  Les liens de navigation interne (#ancre) n'ont pas de sens imprimés, mais
    #  on garde le texte : les retirer amputerait des phrases.
    return corps


def styles_du_manuel(html: str) -> str:
    """La feuille de style du manuel, reprise telle quelle.

    🔴 Reprise, jamais réécrite. Le PDF doit ressembler au manuel : redessiner
    ses cartes et ses couleurs ici créerait une seconde charte, qui dériverait à
    la première retouche de l'écran.
    """
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", html, re.S | re.I))


def sommaire(html: str) -> list[str]:
    """Les titres de niveau 2, DANS L'ORDRE DU DOCUMENT.

    ⚠️ Construit depuis le document, jamais tenu à la main : une table des
    matières recopiée est une table de plus, et ce manuel vient de perdre toutes
    les siennes (#651).
    """
    corps = corps_du_manuel(html)
    titres = []
    for brut in _TITRES.findall(corps):
        #  `unescape` avant de normaliser : le manuel écrit « Une question&nbsp;? »
        #  en typographie française, et un sommaire qui afficherait l'entité
        #  brute trahirait sa fabrication.
        titre = unescape(_BALISES.sub("", brut))
        titre = re.sub(r"\s+", " ", titre).strip()
        if titre:
            titres.append(titre)
    return titres


def version_du_manuel(html: str) -> str:
    """La version imprimée dans le pied du manuel, ou une chaîne vide."""
    trouve = _VERSION.search(_BALISES.sub(" ", html))
    return trouve.group(1) if trouve else ""


def _css(styles_manuel: str) -> str:
    """Le CSS du PDF : celui du manuel, plus ce que l'impression exige."""
    return f"""
{PALETTE_CSS}
{styles_manuel}

@page {{
  size: A4;
  margin: 18mm 16mm 20mm;
  @bottom-center {{
    content: counter(page) " / " counter(pages);
    font-family: {FONT_SANS};
    font-size: 8pt;
    color: var(--light-muted);
  }}
}}
/*  La page de garde n'a ni marge ni numéro : elle est une affiche. */
@page garde {{ margin: 0; @bottom-center {{ content: none; }} }}

body {{
  font-family: {FONT_SANS};
  color: var(--ink);
  background: #fff;
  font-size: 10pt;
  line-height: 1.5;
}}

/*  🔴 CE QUE L'IMPRESSION IMPOSE, et que l'écran n'a pas. La barre latérale et
    les boutons d'action sont des gestes d'écran : sur le papier, ils ne mènent
    nulle part. Le repli des blocs, lui, est levé À LA COMPOSITION (voir
    `corps_du_manuel`) — pas ici : ce qui suit habille le résultat. */
.sidebar, .hero-actions, .aide-liens {{ display: none !important; }}
.ecran-detail {{ margin-top: 2mm; border-top: 1px dashed var(--border); padding-top: 2mm; }}
.ecran-detail-titre {{
  font-size: 8.5pt;
  font-weight: 700;
  color: var(--gold);
  text-transform: uppercase;
  letter-spacing: .08em;
  margin: 0 0 1.5mm;
}}
.ecran-detail-corps {{ margin-top: 0; }}

.ecran-grid {{ display: block; }}
.ecran-card {{
  page-break-inside: avoid;
  margin-bottom: 6mm;
  border: 1px solid var(--border);
  border-radius: 4mm;
  padding: 4mm 5mm;
}}
.ecran-icone {{ width: 7mm; height: 7mm; color: var(--navy); }}
.quick-grid, .persona-grid {{ display: block; }}
.quick-card, .persona-card {{
  page-break-inside: avoid;
  margin-bottom: 4mm;
  border: 1px solid var(--border);
  border-radius: 3mm;
  padding: 3mm 4mm;
}}
.chapter, .quick-start, .hero {{
  page-break-inside: auto;
  background: none;
  color: var(--ink);
  padding: 0;
  margin-bottom: 8mm;
}}
.hero h1 {{ color: var(--navy); font-family: {FONT_SERIF}; }}
.hero p, .hero-note {{ color: var(--muted); }}
.hero-kicker {{ color: var(--gold) !important; }}
/*  Les pastilles du bandeau d'accueil sont blanches sur fond bleu à l'écran :
    sur le papier, le fond disparaît et elles deviennent invisibles. Repeintes
    plutôt que masquées — elles portent trois phrases utiles. */
.hero-cards {{ display: block; margin-top: 4mm; }}
.hero-card {{
  display: inline-block;
  margin: 0 2mm 2mm 0;
  padding: 1.5mm 3mm;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
  font-size: 8.5pt;
}}
h2 {{
  font-family: {FONT_SERIF};
  color: var(--navy);
  font-size: 15pt;
  page-break-after: avoid;
}}
h3 {{ page-break-after: avoid; }}
a {{ color: var(--navy); text-decoration: none; }}

/* ── Page de garde ────────────────────────────────────────────────────── */
.garde {{
  page: garde;
  page-break-after: always;
  height: 297mm;
  position: relative;
  background: var(--navy);
  color: #fff;
  text-align: center;
}}
/*  Le bandeau doré : la seule ligne de couleur chaude de la charte, employée
    ici comme sur les affiches de hall — un rappel, pas une décoration. */
.garde::after {{
  content: "";
  position: absolute; left: 0; right: 0; bottom: 0;
  height: 14mm;
  background: var(--gold);
}}
/*  Un liseré doré en haut répond à celui du pied : la page est tenue par ses
    deux bords, pas posée sur un fond. */
.garde::before {{
  content: "";
  position: absolute; left: 0; right: 0; top: 0;
  height: 4mm;
  background: var(--gold);
}}
.garde-logo {{ padding-top: 34mm; }}
/*  Médaillon : le logo est blanc sur bleu, il se perdrait sans un fond clair. */
.garde-medaillon {{
  width: 30mm; height: 30mm;
  margin: 0 auto;
  border-radius: 50%;
  background: rgba(255, 255, 255, .08);
  border: 1px solid rgba(255, 255, 255, .18);
  display: flex;
  align-items: center;
  justify-content: center;
}}
.garde-surtitre {{
  font-size: 9.5pt;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--gold);
  margin-top: 10mm;
}}
.garde-titre {{
  font-family: {FONT_SERIF};
  font-size: 34pt;
  line-height: 1.1;
  margin: 4mm 22mm 0;
  letter-spacing: .01em;
}}
.garde-sous {{
  font-size: 12pt;
  color: #C7D2E0;
  margin: 6mm 28mm 0;
  line-height: 1.6;
}}
.garde-filet {{
  width: 26mm; height: 2px;
  background: var(--gold);
  margin: 10mm auto;
}}
.garde-qr {{ margin-top: 12mm; }}
.garde-qr img {{
  width: 34mm; height: 34mm;
  background: #fff;
  padding: 3mm;
  border-radius: 3mm;
}}
.garde-qr p {{
  font-size: 9.5pt;
  color: #C7D2E0;
  margin-top: 4mm;
}}
.garde-qr strong {{ color: #fff; }}
.garde-pied {{
  position: absolute;
  left: 0; right: 0; bottom: 20mm;
  font-size: 9pt;
  color: #A8B6C8;
}}

/* ── Sommaire ─────────────────────────────────────────────────────────── */
.sommaire {{ page-break-after: always; }}
.sommaire h2 {{ margin-bottom: 6mm; }}
.sommaire ol {{ list-style: none; padding: 0; counter-reset: som; }}
.sommaire li {{
  counter-increment: som;
  padding: 2.5mm 0;
  border-bottom: 1px dotted var(--border);
  font-size: 11pt;
}}
.sommaire li::before {{
  content: counter(som) ".";
  color: var(--gold);
  font-weight: 700;
  margin-right: 3mm;
}}

/* ── Mentions ─────────────────────────────────────────────────────────── */
.mentions {{
  page-break-before: always;
  border-top: 3px solid var(--gold);
  padding-top: 6mm;
  font-size: 9pt;
  color: var(--muted);
}}
.mentions h2 {{ font-size: 13pt; }}
.mentions dt {{ font-weight: 700; color: var(--ink); margin-top: 3mm; }}
.mentions dd {{ margin: 0 0 1mm; }}
.mentions .avert {{
  margin-top: 6mm;
  padding: 3mm 4mm;
  background: var(--bg);
  border-left: 3px solid var(--gold);
}}
"""


def _garde(site_nom: str, site_url: str, version: str, edite_le: date) -> str:
    qr = qr_data_uri(site_url)
    bloc_qr = (
        f'<div class="garde-qr"><img src="{qr}" alt="">'
        f"<p>Ouvrez le site en photographiant ce code<br>"
        f'<strong>{escape(site_url)}</strong></p></div>'
        if qr
        else f'<div class="garde-qr"><p><strong>{escape(site_url)}</strong></p></div>'
    )
    return f"""
<section class="garde">
  <div class="garde-logo"><div class="garde-medaillon">{logo_svg(64)}</div></div>
  <p class="garde-surtitre">{escape(site_nom)}</p>
  <h1 class="garde-titre">Manuel<br>utilisateur</h1>
  <p class="garde-sous">L'extranet de votre résidence.<br>
     Trouver vite ce dont vous avez besoin.</p>
  <div class="garde-filet"></div>
  {bloc_qr}
  <p class="garde-pied">Édition du {date_longue(edite_le)}{
      f" · {escape(version)}" if version else ""}</p>
</section>
"""


def _sommaire(titres: list[str]) -> str:
    if not titres:
        return ""
    lignes = "".join(f"<li>{escape(t)}</li>" for t in titres)
    return f'<section class="sommaire"><h2>Sommaire</h2><ol>{lignes}</ol></section>'


def _mentions(site_nom: str, site_url: str, version: str, edite_le: date) -> str:
    """Les mentions du feuillet — ce qu'un document imprimé doit porter.

    ⚠️ L'avertissement de péremption n'est pas une formule : un PDF imprimé
    survit à l'écran qu'il décrit, et c'est le seul endroit où on peut le dire au
    lecteur qui l'aura sous les yeux dans deux ans.
    """
    return f"""
<section class="mentions">
  <h2>À propos de ce document</h2>
  <dl>
    <dt>Document</dt>
    <dd>Manuel utilisateur de {escape(site_nom)}{f" — {escape(version)}" if version else ""}.</dd>
    <dt>Édité le</dt><dd>{date_longue(edite_le)}</dd>
    <dt>Éditeur</dt>
    <dd>Le conseil syndical de la copropriété. Mentions légales complètes et
        politique de confidentialité sur {escape(site_url)}/mentions-legales.</dd>
    <dt>Diffusion</dt>
    <dd>Document à usage interne, destiné aux résidents. Il décrit un site dont
        l'accès est réservé aux personnes inscrites.</dd>
  </dl>
  <p class="avert"><strong>Ce feuillet est une photographie.</strong> Le site
     évolue ; la version en ligne, elle, est toujours à jour —
     {escape(site_url)}/manuel-utilisateur.html. En cas de désaccord entre ce
     papier et l'écran, c'est l'écran qui a raison.</p>
</section>
"""


def composer_html(
    site_nom: str,
    site_url: str,
    *,
    html_manuel: str | None = None,
    edite_le: date | None = None,
) -> str:
    """Le document imprimable, AVANT rendu — garde, sommaire, contenu, mentions.

    🔴 Séparée du rendu à dessein. WeasyPrint exige des bibliothèques système
    (cf. `api/Dockerfile`) qu'un poste de développement Windows n'a pas : sans
    cette coupure, la composition ne serait éprouvable que dans un conteneur,
    c'est-à-dire jamais pendant qu'on l'écrit.

    C'est la même leçon que `courriel_ingestion` — la décision se teste, le tuyau
    se branche.
    """
    html = html_manuel if html_manuel is not None else lire_manuel()
    edite_le = edite_le or date.today()
    version = version_du_manuel(html)

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Manuel utilisateur — {escape(site_nom)}</title>
<style>{_css(styles_du_manuel(html))}</style>
</head><body>
{_garde(site_nom, site_url, version, edite_le)}
{_sommaire(sommaire(html))}
{corps_du_manuel(html)}
{_mentions(site_nom, site_url, version, edite_le)}
</body></html>"""


def generer_manuel_pdf(
    site_nom: str,
    site_url: str,
    *,
    html_manuel: str | None = None,
    edite_le: date | None = None,
) -> bytes:
    """Le manuel complet en PDF."""
    return html_to_pdf(
        composer_html(site_nom, site_url, html_manuel=html_manuel, edite_le=edite_le)
    )
