"""🔒 La cloche n'a qu'une porte, et elle obéit au profil (#1187, 23/09/2026).

Règle posée par l'utilisateur : « aucun mail (ou autre notification) n'est
envoyé autre que ceux précisés dans la section Diffusion ou dans sa
configuration profil ». Vingt-deux `Notification(...)` étaient écrits à la
main dans treize fichiers et partaient sans condition.

Ce contrôle refuse :
1. un `Notification(` construit ailleurs que dans `utils/cloche.py` ;
2. un `sonner_systeme` dont le motif n'est pas déclaré dans `MOTIFS_SYSTEME`.
"""

from __future__ import annotations

import ast
import pathlib

from app.utils.cloche import MOTIFS_SYSTEME

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"
PORTE = RACINE / "utils" / "cloche.py"


def _appels(nom: str):
    for fichier in RACINE.rglob("*.py"):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == nom:
                yield fichier, n


def test_aucune_notification_construite_hors_de_la_porte():
    hors = [f"{f.relative_to(RACINE)}:{n.lineno}" for f, n in _appels("Notification") if f != PORTE]
    assert not hors, (
        "Notification construite hors de utils/cloche — passer par `sonner` (le profil "
        f"décide) ou `sonner_systeme` (motif déclaré) : {hors}"
    )


def test_la_porte_elle_meme_est_vue():
    """Cas zéro : si le relevé ne voyait rien, le test ci-dessus passerait à vide."""
    assert any(f == PORTE for f, _ in _appels("Notification"))
    assert sum(1 for _ in _appels("sonner")) >= 5


def test_chaque_motif_systeme_est_declare():
    motifs = []
    for f, n in _appels("sonner_systeme"):
        if f == PORTE:
            continue
        premier = n.args[1] if len(n.args) > 1 else None
        assert isinstance(premier, ast.Constant), f"{f.name}:{n.lineno} : motif non littéral"
        motifs.append(premier.value)
    inconnus = sorted(set(motifs) - set(MOTIFS_SYSTEME))
    assert not inconnus, f"motifs système non déclarés : {inconnus}"
    assert motifs, "aucun envoi système relevé — le contrôle ne voit rien"
