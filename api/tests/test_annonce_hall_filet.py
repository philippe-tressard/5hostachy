"""Le filet doré du bandeau de périmètre est peint UNE fois — et visible une fois.

## Quatre tentatives, et rien qui les verrouille

Le même défaut a été signalé **trois fois à l'écran** — « deux barres orange à
gauche du périmètre » — et corrigé quatre fois :

| | Ce qui a été tenté | Résultat |
|---|---|---|
| 18/08/2026 | bordure d'un seul côté, rayon retiré | deux segments |
| 10/09/2026 | dégradé à deux positions (CSS Images 4) | déclaration jetée, **rien** peint |
| 11/09/2026 | dégradé à deux arrêts | deux barres, encore |
| 11/09/2026 (#897) | **le filet devient un ÉLÉMENT** : deux rectangles pleins | ✅ |

Le commentaire de `annonce_hall.py` dit pourquoi les trois premières ont échoué :
*« un mécanisme que je ne peux pas observer depuis ce poste — WeasyPrint ne s'y
installe pas, et j'ai corrigé deux fois à l'aveugle »*. C'est exact, et c'est
justement ce qui manquait : **une mesure**. Ce fichier la fournit.

## 🔴 La cause n'est PAS corrigée — elle est rendue invisible

Mesuré dans le flux du PDF, la quatrième version peint le doré **deux fois** :

    x=46.68 y=135.39 l=4.54 h=25.31   ← le filet, visible
    x=46.68 y=138.22 l=0.00 h=11.33   ← un second, de largeur NULLE

Le second vient d'un comportement de WeasyPrint qu'aucune des quatre tentatives
n'a nommé : **un enfant `inline` d'un conteneur `flex` est emballé dans un bloc
anonyme qui hérite de son fond**, et les deux sont peints. `.chip-filet` est un
`<span>` dans un `.chip-perimetre` en `display: flex` : la condition est
toujours réunie. Si elle ne se voit plus, c'est que la boîte interne n'a aucun
contenu, donc une largeur de zéro.

⚠️ **Lui donner un jour un contenu, un `padding` ou un `min-width` ramène la
cinquième occurrence.** Ce contrôle ne demande donc pas « y a-t-il un seul
rectangle doré ? » — il y en a deux, et c'est acceptable — mais **« un seul
est-il VISIBLE ? »**. C'est la question que l'utilisateur pose depuis le 18 août.

## Ce qu'il ne peut pas vérifier

Le poste de développement n'a pas les bibliothèques natives de WeasyPrint (elles
sont dans `api/Dockerfile`) : le contrôle y renvoie INCONNU (`skip`), jamais OK.
La CI installe pango/cairo — c'est là qu'il fait barrage, et
`test_weasyprint_present_en_ci` refuse qu'il s'y abstienne (`tests/aides_pdf.py`).

Porté le 25/09/2026 depuis la branche `claude/pdf-orange-bars-affiche-yluuiq`
(commit `64b88cd`, 15/09), jamais fusionnée (#1299). `pytest.importorskip` y
laissait passer l'`OSError` d'un WeasyPrint installé sans ses bibliothèques :
le garde partagé la couvre.
"""

from __future__ import annotations

import re

import pytest

from app.utils.annonce_hall import FORMATS, construire_html
from tests.aides_pdf import besoin_weasyprint, exiger_weasyprint_en_ci
from app.utils.pdf_theme import PALETTE_CSS

_ARGUMENTS = dict(
    titre="Rénovation complète de l’ascenseur du bâtiment 1 du 28/9 au 16/10",
    message_html="<p>La société Koné informe le Conseil syndical que les travaux "
    "commenceront le lundi 28 septembre.</p>",
    perimetre_label="Bât. 1 › Ascenseur",
    site_nom="5Hostachy",
    site_url="5hostachy.fr",
)


def _dore() -> tuple[float, float, float]:
    """La couleur du filet, LUE dans la palette imprimable.

    🔴 La recopier ferait de ce contrôle une seconde source de vérité : le jour
    où la charte changerait de doré, il chercherait une couleur que plus rien ne
    peint et passerait au vert en ne mesurant RIEN. C'est le cas zéro le plus
    coûteux — un contrôle qui réussit parce qu'il ne trouve pas son sujet.
    """
    trouve = re.search(r"--gold:\s*#([0-9A-Fa-f]{6})", PALETTE_CSS)
    assert trouve, "Cas zéro : `--gold` a disparu de la palette — contrôle inopérant."
    brut = trouve.group(1)
    return tuple(round(int(brut[i : i + 2], 16) / 255, 4) for i in (0, 2, 4))


def _rectangles_peints(
    pdf: str,
) -> list[tuple[tuple[float, float, float], float, float, float, float]]:
    """(couleur, x, y, largeur, hauteur) de chaque rectangle réellement REMPLI.

    ⚠️ Un mini-interpréteur, et il le faut : la couleur est posée par un
    opérateur (`rg`) parfois très loin du rectangle qu'elle peindra, avec des
    `q`/`Q` qui l'empilent et la restaurent entre les deux. Une expression
    régulière qui exigerait les deux côte à côte ne trouve rien — c'est ce
    qu'elle a fait au premier essai, et « zéro aplat doré » se lit comme un
    succès alors que c'est une cécité.

    🔴 **TOUS les flux, pas le plus long.** La première écriture prenait
    `max(flux, key=len)`, en supposant que la page est le plus gros morceau du
    document. C'est vrai en A5 et faux en A4, A6 et A7, où une police embarquée
    pèse davantage : le contrôle lisait alors un fichier de fontes, n'y trouvait
    aucun rectangle, et le cas zéro l'a dit. Les flux binaires ne portent aucun
    de ces opérateurs — les parcourir tous ne coûte que du temps.
    """
    couleur: tuple[float, float, float] | None = None
    pile: list[tuple[float, float, float] | None] = []
    dernier: tuple[float, float, float, float] | None = None
    peints = []
    lignes = []
    for flux in re.findall(r"stream\r?\n(.*?)endstream", pdf, re.S):
        lignes.extend(flux.split("\n"))
    for ligne in lignes:
        t = ligne.strip()
        if t == "q":
            pile.append(couleur)
        elif t == "Q":
            couleur = pile.pop() if pile else None
        elif re.fullmatch(r"[\d.]+ [\d.]+ [\d.]+ rg", t):
            couleur = tuple(round(float(v), 4) for v in t.split()[:3])
        elif re.fullmatch(r"[-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+ re", t):
            dernier = tuple(float(v) for v in t.split()[:4])
        elif t in ("f", "f*") and dernier is not None and couleur is not None:
            peints.append((couleur, *dernier))
    return peints


#: Le fond du bandeau de périmètre, écrit en clair dans `annonce_hall.py` — il
#: n'appartient à aucune variable de la palette, d'où sa recopie ici. Le contrôle
#: échoue si la teinte change, plutôt que de mesurer une page vide : c'est un
#: appariement volontaire, pas un oubli de factorisation.
FOND_BANDEAU = "#F0EDE6"


def _hex_vers_rgb(brut: str) -> tuple[float, float, float]:
    brut = brut.lstrip("#")
    return tuple(round(int(brut[i : i + 2], 16) / 255, 4) for i in (0, 2, 4))


def _chevauchent(a, b) -> bool:
    """Les deux rectangles partagent-ils une surface ? (se toucher suffit)"""
    (_, ax, ay, al, ah), (_, bx, by, bl, bh) = a, b
    return ax <= bx + bl and bx <= ax + al and ay <= by + bh and by <= ay + ah


def _filets(format_effectif: str):
    """Les rectangles dorés DU BANDEAU de périmètre, et eux seuls.

    🔴 **La mesure est recentrée sur le bandeau, pas sur la page** — première
    écriture corrigée le 15/09/2026. Compter les rectangles dorés de la feuille
    entière en trouvait TROIS : le filet, son doublon de largeur nulle… et le
    logo, qui porte légitimement un aplat doré (le QR aussi selon le format). Le
    contrôle échouait donc sur un PDF correct, en désignant un coupable qui
    n'avait rien fait.

    La question n'a jamais été « combien d'or sur la feuille ? » mais « combien
    de barres à gauche du périmètre ? ». On repère donc le bandeau par son fond
    beige, et l'on ne retient que le doré qui le touche.
    """
    import weasyprint  # différé : les tests qui l'appellent portent `besoin_weasyprint`

    html = construire_html(format_effectif=format_effectif, **_ARGUMENTS)
    pdf = weasyprint.HTML(string=html).write_pdf(uncompressed_pdf=True).decode("latin-1")

    peints = _rectangles_peints(pdf)
    fond = _hex_vers_rgb(FOND_BANDEAU)
    bandeaux = [r for r in peints if r[0] == fond]
    assert len(bandeaux) == 1, (
        f"Cas zéro : {len(bandeaux)} fond(s) de bandeau {FOND_BANDEAU} dans le PDF "
        f"{format_effectif}, au lieu d'un. Le repère sur lequel ce contrôle "
        "s'appuie n'existe plus — il ne mesure donc plus le bandeau, et ne peut "
        "rien conclure sur son filet."
    )
    dore = _dore()
    return [r for r in peints if r[0] == dore and _chevauchent(r, bandeaux[0])]


def test_weasyprint_present_en_ci():
    exiger_weasyprint_en_ci()


@besoin_weasyprint
@pytest.mark.parametrize("format_effectif", FORMATS)
def test_un_seul_filet_dore_est_VISIBLE(format_effectif: str):
    """🔴 Le contrôle central — la question posée trois fois à l'écran."""
    dores = _filets(format_effectif)

    #  Cas zéro : l'affiche porte un filet doré. N'en trouver AUCUN ne veut pas
    #  dire « pas de doublon », cela veut dire que la lecture est cassée — ou
    #  que le filet a disparu du PDF, ce qui est arrivé le 10/09/2026.
    assert dores, (
        f"Cas zéro : aucun rectangle doré dans le PDF {format_effectif}. Soit "
        "l'extraction ne mesure plus rien, soit le filet ne se peint plus du "
        "tout — c'est ce qui s'est produit le 10/09/2026, quand WeasyPrint a "
        "rejeté la déclaration entière en silence."
    )

    visibles = [d for d in dores if d[3] > 0 and d[4] > 0]
    assert len(visibles) == 1, (
        f"{len(visibles)} filets dorés VISIBLES sur l'affiche {format_effectif}, "
        "au lieu d'un seul :\n  "
        + "\n  ".join(
            f"x={x:.2f} y={y:.2f} l={larg:.2f} h={h:.2f}" for _, x, y, larg, h in visibles
        )
        + "\n\n  C'est le défaut signalé trois fois à l'écran — « deux barres "
        "orange à gauche du périmètre ».\n"
        "  Cause : WeasyPrint emballe un enfant `inline` d'un conteneur `flex` "
        "dans un bloc anonyme\n  qui hérite de son fond, et peint les deux. "
        "`.chip-filet` est un `<span>` dans un\n  `.chip-perimetre` en "
        "`display: flex` — la condition est toujours réunie, et le second\n"
        "  exemplaire n'était invisible que parce que sa largeur valait zéro.\n"
        "  Correctif : donner à l'élément un `display` de niveau bloc, ou lui "
        "retirer ce qui vient\n  de lui donner une largeur."
    )


@besoin_weasyprint
@pytest.mark.parametrize("format_effectif", FORMATS)
def test_le_filet_touche_le_HAUT_et_le_BAS_du_bandeau(format_effectif: str):
    """Un filet plus court que sa boîte se lit comme un défaut d'impression.

    C'est ce que donnait la version à bordure : le trait s'arrêtait avant les
    coins arrondis. `align-items: stretch` le fait courir sur toute la hauteur —
    ce contrôle mesure que c'est bien le cas, plutôt que de faire confiance à la
    déclaration.
    """
    visibles = [d for d in _filets(format_effectif) if d[3] > 0 and d[4] > 0]
    assert len(visibles) == 1, "Contrôle non mesurable : voir le test précédent."
    _, _, _, largeur, hauteur = visibles[0]
    assert hauteur > largeur * 3, (
        f"Le filet fait {largeur:.2f} × {hauteur:.2f} pt : il ne court pas sur la "
        "hauteur du bandeau. Un trait qui s'arrête avant les coins se lit comme "
        "un défaut d'impression — c'est ce que donnait la version à bordure."
    )
