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
from app.utils.manuel_pdf_css import css_du_pdf
from app.utils.pdf_theme import (
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
_TITRES = re.compile(r"<h([23])([^>]*)>(.*?)</h\1>", re.S | re.I)
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
    corps = re.sub(r"<details([^>]*)>", r"<div\1>", corps, flags=re.I)
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


def _ancre(indice: int) -> str:
    """L'identifiant posé sur un titre pour que le sommaire puisse le viser.

    Un compteur, pas un slug du titre : deux écrans peuvent porter le même mot,
    et un identifiant en double ferait pointer deux entrées au même endroit.
    """
    return f"som-{indice}"


def titres_ancres(html: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Le corps AVEC des ancres, et la liste `(niveau, titre, ancre)`.

    🔴 Les deux sont rendus ENSEMBLE, et c'est délibéré : un sommaire dont les
    ancres seraient calculées séparément du corps pointerait à côté au premier
    titre ajouté. Ici, l'identifiant est posé et relevé dans la même passe — ils
    ne peuvent pas diverger.

    ⚠️ Niveaux 2 ET 3 : les quinze écrans sont des `<h3>`. Un sommaire qui
    s'arrêterait au niveau 2 n'offrirait que trois entrées, et ne permettrait pas
    de trouver « Accès & badges » — c'est-à-dire ce pour quoi on ouvre un
    sommaire.
    """
    corps = corps_du_manuel(html)
    releve: list[tuple[int, str, str]] = []

    def poser(m: re.Match) -> str:
        niveau, attrs, contenu = int(m.group(1)), m.group(2), m.group(3)
        #  `unescape` avant de normaliser : le manuel écrit « Une question&nbsp;? »
        #  en typographie française, et un sommaire qui afficherait l'entité
        #  brute trahirait sa fabrication.
        titre = re.sub(r"\s+", " ", unescape(_BALISES.sub("", contenu))).strip()
        if not titre:
            return m.group(0)
        ancre = _ancre(len(releve))
        releve.append((niveau, titre, ancre))
        return f'<h{niveau}{attrs} id="{ancre}">{contenu}</h{niveau}>'

    return _TITRES.sub(poser, corps), releve


def sommaire(html: str) -> list[str]:
    """Les titres du document, dans l'ordre. Conservé pour la lisibilité des tests."""
    return [titre for _, titre, _ in titres_ancres(html)[1]]


def version_du_manuel(html: str) -> str:
    """La version imprimée dans le pied du manuel, ou une chaîne vide."""
    trouve = _VERSION.search(_BALISES.sub(" ", html))
    return trouve.group(1) if trouve else ""


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


def _sommaire(releve: list[tuple[int, str, str]]) -> str:
    """Le sommaire, à DEUX niveaux et avec les numéros de page.

    🔴 Les numéros ne sont pas calculés ici — ils ne peuvent pas l'être : on ne
    sait pas encore combien de pages fera le document. C'est `target-counter()`
    qui les résout au moment de la mise en page, une fonctionnalité CSS Paged
    Media que WeasyPrint implémente. Un numéro écrit à la main serait faux dès
    la première phrase ajoutée au manuel.
    """
    if not releve:
        return ""
    lignes = "".join(
        f'<li class="som-n{niveau}"><a href="#{ancre}">{escape(titre)}</a></li>'
        for niveau, titre, ancre in releve
    )
    return (
        '<section class="sommaire"><h2>Sommaire</h2>'
        f"<ol>{lignes}</ol></section>"
    )


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
    #  Le corps et le relevé viennent de la MÊME passe : voir `titres_ancres`.
    corps, releve = titres_ancres(html)

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Manuel utilisateur — {escape(site_nom)}</title>
<style>{css_du_pdf(styles_du_manuel(html))}</style>
</head><body>
{_garde(site_nom, site_url, version, edite_le)}
{_sommaire(releve)}
{corps}
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
