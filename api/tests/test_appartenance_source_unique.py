"""Une règle d'appartenance ne s'écrit pas chez un routeur.

## Pourquoi (#1028, point 2)

`test_autorisation.py` refuse tout `Depends` local — et il est vert. Mais les
règles d'**appartenance** ne sont pas des `Depends` : ce sont des fonctions
ordinaires, appelées au début d'un geste, et il ne les voyait donc pas. Deux
d'entre elles vivaient chez des routeurs, `routers/bailleur/commun.py` et
`routers/acces/resident.py`.

Elles sont dans `auth/appartenance.py` depuis ce lot — **sans être fondues**, et
c'est le point : elles divergent sur trois axes (le champ de propriété, l'accès
du conseil syndical, le code de refus), et les réunir aurait demandé quatre
paramètres de variation. Ce qu'elles gagnent n'est pas une abstraction, c'est un
**lieu** : côte à côte, on voit que l'une répond 403 et l'autre 404, et pourquoi.

## Ce que ce test refuse

Une comparaison entre un champ d'objet et `user.id` qui **gouverne une levée
HTTP**, écrite hors de `auth/`. C'est la conjonction qui compte : comparer est
banal, lever est banal ; décider d'un refus sur une appartenance est une règle
d'autorisation, et `standards/03` §1 dit où elle vit.

⚠️ Ce qu'il ne voit PAS, et il faut le savoir : une règle qui ne compare pas à
`user.id` — « seul l'aidant accepte une délégation » compare à `aidant_id`, « un
ticket non ouvert n'est modifiable que par l'admin » ne compare rien du tout.
Elles restent chez leurs routeurs, et le ticket les nomme. Les couvrir demanderait
de reconnaître « un champ qui désigne une personne », ce qu'aucun motif ne sait
faire sans se tromper (`standards/04` §12).
"""

import ast
from pathlib import Path

from tests.aides_sources import modules_app

RACINE = Path(__file__).resolve().parents[1] / "app"

#: Le seul endroit où une règle d'appartenance peut s'écrire.
SOURCE = "auth/appartenance.py"


def _regles_hors_source() -> list[str]:
    """Les levées gouvernées par une comparaison à `user.id`, hors `auth/`."""
    fautes = []
    for module in modules_app():
        chemin = module.rel
        if chemin.startswith("auth/"):
            continue
        if "user.id" not in module.source:
            continue
        arbre = module.arbre
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.If):
                continue
            condition = ast.unparse(noeud.test)
            #  « un champ d'objet comparé à l'utilisateur courant »
            if not ("user.id" in condition and ("!=" in condition or "==" in condition)):
                continue
            #  … qui gouverne une levée HTTP, et pas autre chose.
            leve = any(
                isinstance(n, ast.Raise) and "HTTPException" in (ast.unparse(n) or "")
                for n in ast.walk(noeud)
            )
            if leve:
                fautes.append(f"app/{chemin}:{noeud.lineno}")
    return fautes


def test_aucune_regle_d_appartenance_hors_du_module_central():
    fautes = _regles_hors_source()
    assert not fautes, (
        "Règle(s) d'appartenance écrite(s) hors de `auth/` :\n"
        + "\n".join(f"  {f}" for f in fautes)
        + f"\n\nElles vivent dans `app/{SOURCE}`, avec les autres : c'est là qu'on "
        f"compare leurs décisions — qui est admis, et si le refus dit « interdit » "
        f"ou « introuvable ». Une règle rangée chez celui qui l'applique est "
        f"invisible au suivant (`standards/03` §1)."
    )


def test_le_module_central_porte_bien_des_regles():
    """Cas zéro : un module vide rendrait le test précédent vert sans rien dire.

    Il suffirait de supprimer `auth/appartenance.py` et de ne plus rien comparer
    à `user.id` nulle part pour que tout passe — en ayant perdu les règles.
    """
    module = RACINE / SOURCE
    assert module.exists(), f"app/{SOURCE} a disparu : les règles n'ont plus de lieu."
    arbre = ast.parse(module.read_text(encoding="utf-8"))
    exigeantes = [
        n.name
        for n in ast.walk(arbre)
        if isinstance(n, ast.FunctionDef)
        and any(
            isinstance(x, ast.Raise) and "HTTPException" in (ast.unparse(x) or "")
            for x in ast.walk(n)
        )
    ]
    assert len(exigeantes) >= 2, (
        f"app/{SOURCE} ne porte plus que {exigeantes} : ce module existe pour qu'on "
        f"COMPARE des règles d'appartenance ; avec une seule, il n'y a rien à comparer "
        f"et le lieu a perdu sa raison d'être."
    )


#  ── Une appartenance qui FILTRE au lieu de lever (#1551) ──────────────────────
#
#  Le test du haut ne voit qu'une comparaison qui gouverne une LEVÉE. La liste des
#  transferts d'une affaire filtrait par `continue` sur la règle même de
#  `exiger_auteur_du_versement` (`v.transfere_par_id != user.id`) : invisible, et
#  libre de diverger le jour où la règle apprend quelque chose — la liste
#  proposerait alors un geste refusé, ou tairait un geste permis.
#
#  On ne cherche pas « toute comparaison à user.id » : la plupart excluent
#  l'auteur d'une notification (« ne pas se prévenir soi-même »), ce qui n'est
#  pas une appartenance. On cherche les champs que le module central compare
#  LUI-MÊME à un utilisateur — lus dans `auth/appartenance.py`, jamais recopiés
#  ici : une règle neuve y étend aussitôt ce contrôle.
#
#  ⚠️ Hors portée, délibérément : la colonne d'une CLASSE dans un `select()`
#  (`LocationBail.bailleur_id == user.id`). C'est la liste « des miens », une
#  autre question que « puis-je agir dessus » — le bail admet le conseil
#  syndical, « mes baux » non. Même arbitrage que `test_regle_acces_source_unique`.


def _comparaisons_a_un_utilisateur(arbre: ast.AST):
    """(champ, ligne) pour chaque `objet.champ ==/!= x.id`, `objet` une instance."""
    for n in ast.walk(arbre):
        if not isinstance(n, ast.Compare) or len(n.ops) != 1:
            continue
        if not isinstance(n.ops[0], (ast.Eq, ast.NotEq)):
            continue
        for a, b in ((n.left, n.comparators[0]), (n.comparators[0], n.left)):
            if not (isinstance(b, ast.Attribute) and b.attr == "id"):
                continue
            if (
                isinstance(a, ast.Attribute)
                and isinstance(a.value, ast.Name)
                and not a.value.id[:1].isupper()  # une instance, pas une colonne de classe
                and a.attr != "id"
            ):
                yield a.attr, n.lineno


def _champs_d_appartenance() -> set[str]:
    """Les champs que le module central compare à un utilisateur."""
    arbre = ast.parse((RACINE / SOURCE).read_text(encoding="utf-8"))
    return {champ for champ, _ in _comparaisons_a_un_utilisateur(arbre)}


def test_les_champs_d_appartenance_se_lisent_dans_le_module_central():
    """Cas zéro : un relevé vide rendrait le test suivant vert sur rien."""
    champs = _champs_d_appartenance()
    assert {"transfere_par_id", "bailleur_id"} <= champs, (
        f"le module central ne compare plus que {sorted(champs)} à un utilisateur : "
        "le relevé a perdu sa portée, ou les règles ont changé de forme"
    )
    copie = "for v in vs:\n    if v.transfere_par_id != user.id:\n        continue\n"
    assert list(_comparaisons_a_un_utilisateur(ast.parse(copie))), (
        "la forme « filtre » n'est plus reconnue"
    )


def test_aucune_appartenance_ne_se_recompare_hors_du_module_central():
    """🔴 Le défaut de #1551 : le filtre des transferts recopiait la règle du geste."""
    champs = _champs_d_appartenance()
    fautes = []
    for module in modules_app():
        if module.rel.startswith("auth/"):
            continue
        if not any(c in module.source for c in champs):
            continue
        for champ, ligne in _comparaisons_a_un_utilisateur(module.arbre):
            if champ in champs:
                fautes.append(f"  app/{module.rel}:{ligne} — `{champ}`")
    assert not fautes, (
        "Une règle d'appartenance du module central est recomparée ailleurs :\n"
        + "\n".join(fautes)
        + f"\n\nAppeler le prédicat de `app/{SOURCE}` — celui que le geste appelle "
        "pour refuser. Une liste qui filtre sur sa propre copie propose ce que le "
        "geste refusera, ou tait ce qu'il permet."
    )
