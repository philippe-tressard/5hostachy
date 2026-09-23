"""Un prédicat de visibilité s'appelle avec SA signature (#1167).

## Le défaut du 23/09/2026

`routers/publications/promotion.py` appelait `publication_visible(session, pub,
user)` ; la fonction prend `(pub, user)`. Python ne le dit qu'à l'exécution —
`TypeError`, donc 500 — et aucun test ne passait par ce chemin : la lecture
d'une actualité qui EXISTE, c'est-à-dire l'appel de chaque lien `#pub-N`.

Ruff ne vérifie pas l'arité. Ce contrôle confronte chaque appel d'une fonction
de `utils/visibility/` à sa définition, dans tout `app/` : une règle d'accès
qui lève au lieu de répondre est une règle qui ne s'applique pas.
"""
from __future__ import annotations

import ast
import pathlib

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def _signatures() -> dict[str, tuple[int, int]]:
    """nom → (arguments positionnels obligatoires, positionnels au total)."""
    sigs: dict[str, tuple[int, int]] = {}
    for p in (_APP / "utils" / "visibility").glob("*.py"):
        for f in ast.parse(p.read_text(encoding="utf-8")).body:
            if isinstance(f, ast.FunctionDef) and not f.name.startswith("_"):
                pos = f.args.posonlyargs + f.args.args
                sigs[f.name] = (len(pos) - len(f.args.defaults), len(pos))
    return sigs


def _appels_faux(source: str, fichier: str, sigs: dict[str, tuple[int, int]]) -> list[str]:
    fautes = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in sigs:
            if any(isinstance(a, ast.Starred) for a in n.args):
                continue
            mini, maxi = sigs[n.func.id]
            if not mini <= len(n.args) <= maxi:
                fautes.append(
                    f"{fichier}:{n.lineno} {n.func.id} — {len(n.args)} argument(s) "
                    f"positionnel(s), la fonction en attend {mini} à {maxi}"
                )
    return fautes


def test_chaque_appel_d_un_predicat_de_visibilite_respecte_sa_signature():
    sigs = _signatures()
    #  Cas zéro : sans définition lue, il n'y aurait rien à comparer.
    assert {"publication_visible", "ticket_visible", "evenement_visible"} <= set(sigs), (
        f"Prédicats introuvables dans utils/visibility/ : {sorted(sigs)}"
    )
    fautes, appels = [], 0
    for p in sorted(_APP.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        source = p.read_text(encoding="utf-8")
        appels += sum(source.count(f"{nom}(") for nom in sigs)
        fautes += _appels_faux(source, p.relative_to(_APP).as_posix(), sigs)
    assert appels >= 20, f"Seulement {appels} appel(s) relevé(s) — portée cassée."
    assert not fautes, "Appel de prédicat de visibilité mal formé :\n  " + "\n  ".join(fautes)


def test_le_releve_voit_le_cas_du_23_09():
    sigs = {"publication_visible": (2, 2)}
    assert _appels_faux("publication_visible(session, pub, user)\n", "x.py", sigs)
    assert not _appels_faux("publication_visible(pub, user)\n", "x.py", sigs)
