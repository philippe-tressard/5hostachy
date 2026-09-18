"""WeasyPrint n'est appelé qu'à UN endroit, et sans les trois arguments à risque.

## Ce que ce test protège

Un appel unique, `HTML(string=html).write_pdf()`, sans `url_fetcher`, sans
`stylesheets` et sans `xmp_metadata`. Il vit dans `utils/pdf_rendu.py` depuis le
16/09/2026 — jusque-là dans `utils/pdf_theme.py`, qui délègue désormais. Ce test
garde donc deux choses d'un seul geste : la surface d'appel du moteur, et le fait
que le rendu s'exécute **hors du process de l'API**, dans un enfant `spawn` qui
n'hérite pas des descripteurs d'`app.db`.

## 🔴 Ce qu'il protégeait EN PLUS, et qui n'existe plus (18/09/2026)

`audit-exceptions.json` tolérait **GHSA-jf6q-chmf-3h3v** (SSRF / lecture de
fichier local dans WeasyPrint ≤ 69) sur un motif vérifiable : l'avis ne concerne
que les applications qui posent un `url_fetcher` restrictif ET passent
`stylesheets=[…]` ou `xmp_metadata=[…]` — ces deux canaux reconstruisant un
fetcher par défaut. Ce test tenait ce motif à chaque exécution, plutôt qu'une
fois dans un fichier que personne ne rouvre.

La dérogation a été **levée** : `weasyprint==70.0` corrige l'avis, et
`api/scripts/check_audit_python.py` ne rapporte plus aucune vulnérabilité ni
aucune exception. Ce test reste — pour la raison qui le précède, et parce que la
surface d'appel d'un moteur de rendu est ce qu'on veut voir grandir sciemment,
pas par accident.

⚠️ La dérogation était datée (`revoirLe: 2026-09-30`) et portait sa condition de
levée. C'est ce qui a permis de la lever en une passe, au lieu d'un « on verra » :
une exception sans date de revue devient une porte qu'on croit fermée.
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
    """La surface d'appel du moteur, revérifiée à chaque exécution."""
    fautifs = [
        (f, nom, sorted(mots & ARGUMENTS_A_RISQUE))
        for f, nom, mots in _appels_weasyprint()
        if mots & ARGUMENTS_A_RISQUE
    ]
    assert not fautifs, (
        f"WeasyPrint est appelé avec un argument que l'avis GHSA-jf6q-chmf-3h3v vise : "
        f"{fautifs}. Ces trois arguments reconstruisent un récupérateur d'URL par "
        "défaut : ils ouvrent le rendu au réseau et au système de fichiers, alors que "
        "tout document de ce dépôt est AUTONOME par construction (CSS en `<style>`, "
        "images en data-URI). Si le besoin est réel, il se décide — pas par un "
        "argument ajouté en passant."
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
        "Dans les deux cas, il ne protège plus rien."
    )
    fichiers = {f for f, _n, _m in appels}
    assert fichiers == {"utils/pdf_rendu.py"}, (
        f"WeasyPrint est appelé hors du module de rendu : {sorted(fichiers)}. Deux "
        "raisons, et chacune suffirait : le contrôle ci-dessus ne "
        "couvre que l'appel unique qu'il a vérifié ; et un appel hors de "
        "`pdf_rendu.py` s'exécuterait DANS le process de l'API, qu'un plantage du "
        "moteur emporterait alors (cf. l'en-tête de ce module)."
    )
