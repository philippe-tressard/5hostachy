"""Un texte composé au serveur ne rend pas une catégorie ou un statut BRUTS.

## Pourquoi (#1350, 26/09/2026)

L'historique d'une affaire écrivait « Catégorie : etude_travaux → panne », et
la notification d'une mise à jour « Nouveau statut : en_cours ». Côté écran,
`npm run lint:categorie-brute` refuse déjà ce défaut ; il ne voit pas le texte
composé ICI, qui part dans l'historique, la cloche ou un courriel.

## Ce qu'il refuse

Une f-string qui interpole `x.categorie` ou `x.statut` TELS QUELS. La forme
conforme passe par une fonction — `libelle_categorie(x.categorie)`,
`STATUT_LABELS.get(...)` — et l'AST la distingue : l'attribut n'est plus
l'expression interpolée, mais son argument.
"""

from __future__ import annotations

import ast
import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"
ATTRIBUTS = {"categorie", "statut"}


def valeurs_brutes(source: str) -> list[int]:
    """Les lignes où une f-string interpole `x.categorie` / `x.statut` nus. PURE."""
    lignes = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.FormattedValue):
            v = noeud.value
            if isinstance(v, ast.Attribute) and v.attr in ATTRIBUTS:
                lignes.append(noeud.lineno)
    return lignes


def test_le_controle_voit_ce_qu_il_doit_voir():
    assert valeurs_brutes('x = f"Catégorie : {t.categorie} → {b.categorie}"') == [1, 1]
    assert valeurs_brutes('x = f"Nouveau statut : {ticket.statut}"') == [1]
    assert valeurs_brutes('x = f"Catégorie : {libelle_categorie(t.categorie)}"') == []
    assert valeurs_brutes('x = f"{LABELS.get(t.statut, t.statut)}"') == []
    assert valeurs_brutes('x = f"{body.statut_souhaite}"') == []


def test_aucun_texte_serveur_ne_rend_une_valeur_brute():
    fichiers = list(RACINE.rglob("*.py"))
    assert len(fichiers) > 50, "cas zéro : le contrôle ne lit plus le code de l'API"
    fautifs = [
        f"{f.relative_to(RACINE)}:{n}"
        for f in fichiers
        for n in valeurs_brutes(f.read_text(encoding="utf-8"))
    ]
    assert not fautifs, (
        "Catégorie ou statut interpolés BRUTS dans un texte — passer par leur "
        "libellé (`libelle_categorie`, `STATUT_LABELS`) : " + ", ".join(fautifs)
    )
