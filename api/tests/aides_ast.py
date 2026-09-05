"""Lire une fonction AVEC ce qu'elle délègue — l'aide que deux tests partageaient.

## Pourquoi cette aide existe (05/09/2026)

`test_apercu_diffusion` et `test_pieces_jointes` vérifient la même propriété par
deux chemins : *l'aperçu et l'envoi composent le message au même endroit*. Tous
deux la mesuraient en cherchant `composer_email(` **dans le corps de
`send_email`**.

Le jour où `send_email` et `send_email_group` ont été factorisées — elles étaient
identiques à 68 % —, la composition est descendue dans `_envoyer_modele`, appelée
par les deux. La propriété n'a pas bougé d'un pouce ; les deux tests sont tombés.

🔴 C'est `standards/04` §35 en situation : **un contrôle qui reconnaît son objet
à un indice de forme devient d'autant plus aveugle que le code est bien
factorisé.** Ici l'indice était « le texte de cette fonction contient cet
appel » — vrai tant que personne ne factorise, c'est-à-dire tant que personne ne
fait ce qu'il faut.

## Ce que cette aide fait, et ce qu'elle ne fait pas

Elle rend le corps d'une fonction **suivi des corps des fonctions du même module
qu'elle appelle**, sur la profondeur demandée. Un test peut alors demander « ce
chemin passe-t-il par `composer_email` ? » sans exiger que ce soit *directement*.

Elle ne fait **pas** d'analyse de flot : elle ne dit pas que l'appel s'exécute,
seulement qu'il est sur le chemin. C'est le même arbitrage que
`check-workflow-envoye.mjs` — un contrôle large sur du code produit des faux
positifs, et un contrôle qu'on apprend à ignorer ne garde plus rien.

⚠️ Elle ne franchit pas les frontières de module : un appel vers un autre fichier
n'est pas suivi. C'est délibéré — la propriété surveillée ici est « au même
endroit », et « ailleurs » est justement ce qu'on veut voir.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _fonctions(source: str) -> dict[str, ast.AST]:
    arbre = ast.parse(source)
    return {
        n.name: n
        for n in ast.walk(arbre)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def corps_de(chemin: Path, nom: str) -> str:
    """Le source de la fonction `nom`, ou lève.

    Un test qui ne trouve pas sa cible doit **échouer**, pas passer en silence
    (`standards/04` §1) : sans cela, renommer la fonction surveillée désarmerait
    le contrôle sans que rien ne le dise.
    """
    source = chemin.read_text(encoding="utf-8")
    fonction = _fonctions(source).get(nom)
    if fonction is None:
        raise AssertionError(
            f"`{nom}` est introuvable dans {chemin.name} — ce test surveillait une "
            "fonction qui n'existe plus, il ne surveillait donc plus rien."
        )
    return ast.get_source_segment(source, fonction) or ""


def corps_avec_delegations(chemin: Path, nom: str, *, profondeur: int = 2) -> str:
    """`corps_de`, plus les corps des fonctions du MÊME module qu'elle appelle.

    `profondeur=2` par défaut : la fonction et ce qu'elle appelle directement.
    C'est ce qu'il faut pour voir à travers une factorisation d'un cran — celle
    qui vient d'avoir lieu — sans embarquer la moitié du module.
    """
    source = chemin.read_text(encoding="utf-8")
    connues = _fonctions(source)
    vues: set[str] = set()
    morceaux: list[str] = []

    def descendre(cible: str, reste: int) -> None:
        if cible in vues or reste <= 0 or cible not in connues:
            return
        vues.add(cible)
        noeud = connues[cible]
        morceaux.append(ast.get_source_segment(source, noeud) or "")
        for n in ast.walk(noeud):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                descendre(n.func.id, reste - 1)

    corps_de(chemin, nom)  # lève si la cible a disparu — le cas zéro de l'aide
    descendre(nom, profondeur)
    return "\n".join(morceaux)
