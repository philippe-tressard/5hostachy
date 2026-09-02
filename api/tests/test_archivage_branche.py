"""Une règle d'archivage DÉCLARÉE doit être LUE par quelqu'un.

## 🔴 Le défaut (02/09/2026)

`utils/archivage.py` porte les **sept** règles du site depuis le 19/08, avec leurs
statuts, leurs dates de référence et leurs tests. C'est un beau module, et il est
juste.

**Deux objets sur sept l'appelaient.** Les cinq autres — ticket, idée, sondage,
événement, affiche de hall — avaient leur règle écrite, testée, documentée… et
personne pour la lire. Aucun contrôle ne pouvait le dire : `test_archivage.py`
éprouve la DÉCISION, pas son emploi, et il passait au vert sur les sept.

C'est le motif de la mémoire projet « PR vide : un titre sans code » — le paquet
est ajouté, le monolithe reste. Et c'est celui que `check-modales.mjs` a été écrit
pour attraper côté front : *« le composant existe » et « le composant est employé »
cessent d'être deux choses différentes*.

## Ce que ce fichier vérifie

Que chaque clé de `REGLES` apparaît dans un appel `est_archivable("<clé>"` quelque
part sous `app/` — hors du module qui les déclare.

⚠️ Il ne vérifie PAS que l'appel est au bon endroit, ni que le drapeau produit
atteint l'écran : c'est le rôle des tests de chaque routeur. Il attrape la forme,
qui est ce qui manque quand on oublie de brancher.

## Les exceptions sont NOMMÉES, et elles ne survivent pas à leur objet

Une règle non branchée n'est pas un défaut si on sait pourquoi — l'écran
correspondant demande un changement visible, à faire constater (R5). Mais une
tolérance sans raison devient un dépotoir : le second test échoue si l'une cesse
de servir, donc le jour où l'objet est branché, il FAUT venir retirer la ligne.
"""
from __future__ import annotations

from pathlib import Path

from app.utils.archivage import REGLES

RACINE = Path(__file__).resolve().parents[1] / "app"
SOURCE = RACINE / "utils" / "archivage.py"

#: Règles déclarées que personne ne lit encore, avec leur raison.
#:
#: 🔴 Chacune demande un changement VISIBLE — l'objet quitte la liste active pour
#: une section Archives — donc à proposer sur un écran, faire constater, puis
#: généraliser (R5 du cadre #430). Suivi en **#515**.
NON_BRANCHEES = {
    "evenement": "#515 — le calendrier a ses propres Archives, à rapprocher de la règle du site.",
    "annonce_hall": "#515 — les affiches envoyées restent en liste.",
}


def _appelants() -> dict[str, list[str]]:
    """Pour chaque clé de règle, les fichiers qui l'invoquent."""
    trouves: dict[str, list[str]] = {cle: [] for cle in REGLES}
    for fichier in RACINE.rglob("*.py"):
        if fichier == SOURCE:
            continue
        texte = fichier.read_text(encoding="utf-8")
        for cle in REGLES:
            if f'est_archivable("{cle}"' in texte or f"est_archivable('{cle}'" in texte:
                trouves[cle].append(str(fichier.relative_to(RACINE)))
    return trouves


def test_les_regles_declarees_sont_lues():
    """🔴 Le contrôle central : une règle inerte est indistinguable d'une absente."""
    #  CAS ZÉRO — sans règles, ce test serait vert sans rien mesurer.
    assert len(REGLES) >= 5, (
        f"{len(REGLES)} règle(s) déclarée(s) : le module a-t-il été vidé ou renommé ? "
        "Ce contrôle ne mesure plus rien."
    )
    trouves = _appelants()
    orphelines = [cle for cle, fichiers in trouves.items() if not fichiers and cle not in NON_BRANCHEES]
    assert not orphelines, (
        "Règle(s) d'archivage déclarée(s) et lue(s) par PERSONNE : "
        + ", ".join(orphelines)
        + ".\n  Une règle inerte est indistinguable d'une règle absente, et elle "
        "passe tous les tests de décision.\n  L'appeler depuis le routeur de "
        "l'objet, ou l'ajouter à NON_BRANCHEES **avec sa raison**."
    )


def test_aucune_exception_ne_survit_a_son_objet():
    """Une tolérance qui ne sert plus fait croire la règle plus poreuse qu'elle n'est."""
    trouves = _appelants()
    inutiles = []
    for cle in NON_BRANCHEES:
        if cle not in REGLES:
            inutiles.append(f"{cle} (la règle n'existe plus)")
        elif trouves[cle]:
            inutiles.append(f"{cle} (branchée dans {', '.join(trouves[cle])})")
    assert not inutiles, (
        "Exception(s) devenue(s) inutile(s), à retirer de NON_BRANCHEES : "
        + ", ".join(inutiles)
        + ".\n  Et #515 avance d'autant : le dire dans le ticket."
    )
