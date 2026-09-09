"""WeasyPrint n'est appelé qu'à UN endroit, et sans les trois arguments à risque.

## Ce que ce test protège

`audit-exceptions.json` tolère **GHSA-jf6q-chmf-3h3v** (SSRF / lecture de fichier
local dans WeasyPrint ≤ 69) sur un motif **vérifiable** : l'avis ne concerne que
les applications qui posent un `url_fetcher` restrictif ET passent
`stylesheets=[…]` ou `xmp_metadata=[…]` à `write_pdf()` — ces deux canaux
reconstruisant un fetcher par défaut, donc contournant le garde-fou.

Ce dépôt n'a qu'un appel, `HTML(string=html).write_pdf()`, sans aucun des trois.

🔴 **Un motif vérifié une fois n'est vérifié qu'une fois.** Le jour où quelqu'un
ajoutera une feuille de style externe ou des métadonnées XMP à un document
imprimable, le motif deviendra faux — et personne ne rouvrira le fichier
d'exceptions pour s'en apercevoir. Ce test transforme « constaté le 09/09/2026 »
en « constaté à chaque exécution ».

⚠️ Il ne dit rien de la version : monter à 70.0 reste la bonne fin de l'histoire,
et c'est ce que dit `leveeSi`. Il dit seulement que la dérogation repose encore sur
ce qu'elle affirme.
"""
from __future__ import annotations

import ast
import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Les arguments qui reconstruisent un fetcher par défaut, d'après l'avis.
ARGUMENTS_A_RISQUE = {"url_fetcher", "stylesheets", "xmp_metadata"}


def _appels_weasyprint():
    """Chaque appel à `HTML(...)` ou `.write_pdf(...)`, avec ses mots-clés."""
    for chemin in RACINE.rglob("*.py"):
        if "__pycache__" in chemin.parts:
            continue
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            if not isinstance(n, ast.Call):
                continue
            nom = (
                n.func.id if isinstance(n.func, ast.Name)
                else n.func.attr if isinstance(n.func, ast.Attribute)
                else None
            )
            if nom in ("HTML", "write_pdf"):
                yield chemin.relative_to(RACINE).as_posix(), nom, {
                    k.arg for k in n.keywords if k.arg
                }


def test_aucun_argument_a_risque_n_est_employe():
    """Le motif de la dérogation, revérifié à chaque exécution."""
    fautifs = [
        (f, nom, sorted(mots & ARGUMENTS_A_RISQUE))
        for f, nom, mots in _appels_weasyprint()
        if mots & ARGUMENTS_A_RISQUE
    ]
    assert not fautifs, (
        f"WeasyPrint est appelé avec un argument que l'avis GHSA-jf6q-chmf-3h3v vise : "
        f"{fautifs}. La dérogation d'`audit-exceptions.json` repose sur leur ABSENCE — "
        "elle est désormais fausse. Monter weasyprint à 70.0 et retirer l'exception."
    )


def test_cas_zero_le_balayage_trouve_bien_l_appel():
    """🔴 Sans appel trouvé, le test ci-dessus passerait en ne mesurant rien.

    C'est le cas zéro de `standards/04` §2 : un contrôle dont le motif ne
    correspond plus à rien ne refuse plus rien, et il ne le dit pas.
    """
    appels = list(_appels_weasyprint())
    assert appels, (
        "aucun appel à `HTML(...)` ni `.write_pdf(...)` trouvé dans `app/` : soit le "
        "rendu PDF a changé de forme, soit ce contrôle ne regarde plus au bon endroit. "
        "Dans les deux cas, il ne protège plus la dérogation."
    )
    fichiers = {f for f, _n, _m in appels}
    assert fichiers == {"utils/pdf_theme.py"}, (
        f"WeasyPrint est appelé hors du thème commun : {sorted(fichiers)}. Le moteur PDF "
        "ne se redéfinit pas ailleurs (CLAUDE.md), et la dérogation ne couvre que "
        "l'appel unique qu'elle a vérifié."
    )
