"""`noeuds` a UNE forme, pour toutes les tâches — et rien ne le disait (#538).

## Le défaut, constaté en production le 20/08/2026

L'écran `Admin → Maintenance` restait sur « Chargement… ». Le serveur, lui,
répondait **200 OK** — trois fois de suite.

La cause : `GET /admin/maintenance/sante` rendait le champ `noeuds` sous **deux
formes**, selon la tâche qui l'avait produit.

| Tâches | Producteur | Forme de `noeuds` |
|---|---|---|
| maintenance, bascule, export | la boucle `par_noeud` | `[{"noeud": …, "statut": …, "derniere": …}]` |
| sauvegarde, télémétrie | `_etat_tache_a_table_propre` | `["rpi2"]` — des CHAÎNES |

🔴 **Personne ne s'en apercevait**, parce que l'écran ne lisait ce champ qu'au
delà d'UN nœud — et la seconde branche n'en a jamais qu'un. Le jour où l'écran a
rendu la sous-ligne dès le premier nœud (#531), il a fait
`n.noeud.toUpperCase()` sur une chaîne : `undefined.toUpperCase` lève, le rendu
du tableau s'interrompt, et l'écran reste sur son état précédent.

⚠️ **Aucun contrôle ne pouvait le voir.** Le schéma de réponse n'est pas typé
(l'endpoint rend un `dict`), la CI ne compare pas deux branches d'un même
endpoint entre elles, et un appel réussi ne révèle rien : la réponse était
parfaitement valide, simplement pas homogène.

## Ce que ces tests verrouillent

Un contrat qui varie selon la ligne n'est pas un contrat. Le consommateur qui
l'ignore ne tombe pas tout de suite — il tombe le jour où il regarde le cas qu'on
n'avait jamais servi.

⚠️ **Mis à jour le 20/08/2026 (#540).** Les deux branches passent désormais par
un assemblage unique (`_entree_sante`). Ce fichier ne vérifie donc plus qu'elles
se *ressemblent* — il vérifie qu'il n'existe **pas d'autre** point d'assemblage.
C'est la mesure la plus forte des deux : deux formes ne peuvent pas diverger si
un seul endroit les produit.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

#  ⚠️ La décision a été extraite du routeur le 20/08/2026 (#542). Ce chemin
#  suit le CODE, pas le fichier d'origine : pointé sur l'ancien, l'analyse
#  trouverait zéro affectation et ce fichier passerait au vert sans rien lire.
SOURCE = pathlib.Path(__file__).parent.parent / "app" / "utils" / "sante_taches.py"

#: Les clés qu'une entrée de `noeuds` doit porter, quelle que soit sa provenance.
#: `portee` et `retard_heures` s'y ajoutent ; ce sont les trois ci-dessous que
#: l'écran lit, et donc celles dont l'absence casse le rendu.
CLES_ATTENDUES = {"noeud", "statut", "derniere"}


def _litteraux_noeuds() -> list[ast.AST]:
    """Toutes les valeurs affectées à la clé « noeuds » dans ce module.

    ⚠️ Par ANALYSE STATIQUE et non par appel : monter une base avec les cinq
    tâches, chacune dans sa table, pour éprouver une homogénéité de forme
    reviendrait à tester l'échafaudage. Ce qui doit être vrai ici est une
    propriété du CODE — toutes les branches rendent la même chose — et elle se
    lit dans le code.
    """
    arbre = ast.parse(SOURCE.read_text(encoding="utf-8"))
    valeurs = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Dict):
            continue
        for cle, valeur in zip(noeud.keys, noeud.values):
            if isinstance(cle, ast.Constant) and cle.value == "noeuds":
                valeurs.append(valeur)
    return valeurs


def test_le_champ_noeuds_existe_bien_dans_ce_module():
    """Cas zéro : si le champ a été renommé, ces tests ne mesurent plus rien.

    Une liste vide ferait passer tous les paramétrages ci-dessous sans rien
    vérifier — c'est `standards/04` §2, appliqué à un test.
    """
    assert _litteraux_noeuds(), (
        "aucune affectation de « noeuds » trouvée : le champ a-t-il changé de "
        "nom ? Ce fichier ne mesurerait plus rien."
    )


def test_le_champ_noeuds_est_assemble_a_UN_SEUL_endroit():
    """🔴 L'invariant qui rend la divergence impossible, et non improbable.

    Ce fichier exigeait d'abord **au moins trois** affectations de `noeuds` — une
    par branche de calcul. C'était la bonne mesure tant que les branches
    composaient chacune leur réponse : il fallait alors vérifier qu'elles se
    ressemblaient.

    Depuis #540, elles passent toutes par `_entree_sante`. Il ne reste que deux
    affectations littérales : la liste vide du cas « aucune exécution », et
    l'assemblage unique. Vérifier qu'elles se ressemblent n'a plus de sens —
    vérifier qu'il n'y en a **pas d'autres** en a un.

    ⚠️ Ce test est plus fort que celui qu'il remplace : deux formes ne peuvent
    plus diverger si un seul endroit les produit. Un troisième point
    d'assemblage rouvrirait #538 à l'identique, et c'est ce qu'il refuse.
    """
    valeurs = _litteraux_noeuds()
    assert len(valeurs) <= 2, (
        f"{len(valeurs)} endroits construisent « noeuds » : la réponse peut de "
        "nouveau porter deux formes (#538). Passer par `_entree_sante`."
    )


def test_aucune_branche_ne_rend_une_liste_de_chaines():
    """🔴 Le défaut exact : `["rpi2"]` au lieu de `[{"noeud": "rpi2", …}]`.

    Une liste de chaînes est indiscernable d'une liste d'objets tant qu'on ne la
    parcourt pas. C'est ce qui l'a rendue invisible pendant des semaines.

    ⚠️ Ce test était `parametrize(range(10))` + `skip` quand l'indice dépassait
    le nombre d'affectations trouvées. Depuis l'assemblage unique il n'en reste
    que deux : **huit cas sautaient à chaque exécution**, et huit SKIP permanents
    se lisent exactement comme « rien à signaler » (`standards/04` §18). Une
    boucle dit la même chose sans rien taire.
    """
    for valeur in _litteraux_noeuds():
        #  Une compréhension de liste dont l'élément est un nom nu
        #  (`[n for n in …]`) produit des chaînes : la forme fautive.
        if isinstance(valeur, ast.ListComp):
            assert not isinstance(valeur.elt, ast.Name), (
                "cette branche rend une liste de CHAÎNES ; l'écran attend des "
                "objets portant au moins " + ", ".join(sorted(CLES_ATTENDUES))
            )
        #  Une liste littérale d'éléments non-dictionnaires, même défaut.
        if isinstance(valeur, ast.List):
            for element in valeur.elts:
                assert isinstance(element, ast.Dict), (
                    "cette branche rend une liste dont un élément n'est pas un objet"
                )


def test_toute_entree_litterale_porte_les_cles_attendues():
    """Un objet qui oublie `statut` ou `derniere` rend une sous-ligne vide.

    Moins spectaculaire qu'une exception, et plus durable : la ligne s'affiche,
    sans son état ni sa date, et se lit comme « rien à signaler ».

    ⚠️ **Ce test ne voit plus l'assemblage principal**, et c'est voulu : depuis
    l'assemblage unique, `noeuds` reçoit un NOM (`detail`), pas un littéral —
    l'analyse statique n'a plus de dictionnaire à inspecter. Les clés sont
    désormais vérifiées **à l'exécution**, sur la fonction pure, par
    `test_sante_taches_periodes.py::test_chaque_sous_ligne_porte_les_cles_attendues`.
    Il reste ici pour refuser qu'un littéral incomplet réapparaisse.
    """
    manques = []
    for valeur in _litteraux_noeuds():
        dicts = []
        if isinstance(valeur, ast.List):
            dicts = [e for e in valeur.elts if isinstance(e, ast.Dict)]
        elif isinstance(valeur, ast.IfExp):
            #  `[…] if noeud else []` — la branche qui porte la liste.
            for branche in (valeur.body, valeur.orelse):
                if isinstance(branche, ast.List):
                    dicts += [e for e in branche.elts if isinstance(e, ast.Dict)]
        for d in dicts:
            cles = {c.value for c in d.keys if isinstance(c, ast.Constant)}
            absentes = CLES_ATTENDUES - cles
            if absentes:
                manques.append(sorted(absentes))
    assert not manques, f"entrée(s) de `noeuds` incomplète(s) : {manques}"
