"""Pas de bouton DANS un lien (#1329, 26/09/2026).

La carte d'un sondage était un `<a>` qui contenait ✏️, ⏹️, 🗑️ et 🔗 : HTML
invalide (un contenu interactif dans un contenu interactif), un lecteur d'écran
y annonçait un lien géant, et chaque geste devait `preventDefault` pour ne pas
ouvrir la fiche. Elle passe au motif du lien ÉTIRÉ sous le contenu.

Le contrôle lit le balisage des composants : tout `<a …>…</a>` qui contient un
`<button` ou un composant qui en rend un (`BoutonLien`) est refusé.
"""

from __future__ import annotations

import pathlib
import re

_FRONT = pathlib.Path(__file__).resolve().parents[2] / "front" / "src"
#: Les composants qui rendent un `<button>` — un lien ne les contient pas non plus.
COMPOSANTS_BOUTONS = ("BoutonLien", "BoutonNouveau", "Pastille")


def liens_a_boutons(source: str) -> list[int]:
    """Les lignes où s'ouvre un lien qui contient un bouton. PURE."""
    fin = source.rfind("</script>")
    balisage = source[fin:] if fin >= 0 else source
    decalage = source[:fin].count("\n") if fin >= 0 else 0
    balisage = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), balisage, flags=re.S)
    motif = re.compile(r"<button\b|<(?:%s)\b" % "|".join(COMPOSANTS_BOUTONS))
    fautes = []
    #  `</a\s*>` : Prettier coupe souvent la fermante (`</a` puis `>` a la ligne).
    for m in re.finditer(r"<a\b[^>]*>(.*?)</a\s*>", balisage, re.S):
        if motif.search(m.group(1)):
            fautes.append(decalage + balisage[: m.start()].count("\n") + 1)
    return fautes


def test_le_controle_voit_la_forme_d_avant():
    avant = (
        '<script>\n</script>\n<a href="/sondages/1" class="carte">\n'
        '<EnteteCarte titre="Q"><BoutonLien /><button>✏️</button></EnteteCarte>\n</a>'
    )
    assert liens_a_boutons(avant) == [3]
    apres = '</script><div class="carte"><a class="lien" href="/s/1"></a><button>✏️</button></div>'
    assert liens_a_boutons(apres) == []
    assert liens_a_boutons("</script><!-- <a><button></button></a> --><p>ok</p>") == []
    #  La fermante coupee par Prettier ferme bien le lien (faux positif du 26/09).
    assert liens_a_boutons('</script><a href="/p"\n>pol</a\n>*<button>x</button>') == []


def test_aucun_lien_ne_contient_de_bouton():
    fichiers = list(_FRONT.rglob("*.svelte"))
    assert len(fichiers) > 100, "cas zéro : le balisage n'est plus lu"
    fautes = [
        f"{f.relative_to(_FRONT)}:{ligne}"
        for f in fichiers
        for ligne in liens_a_boutons(f.read_text(encoding="utf-8"))
    ]
    assert not fautes, "Un bouton DANS un lien (HTML invalide) :\n  " + "\n  ".join(fautes)
