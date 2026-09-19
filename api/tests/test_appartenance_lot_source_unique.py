"""« Ce lot est-il le mien ? » s'écrit à UN endroit, et il exige le lien ACTIF (#1028).

## 🔴 Le défaut que ce contrôle refuse

La question était écrite **deux fois**, et les deux écritures ne disaient pas la
même chose :

| Écriture | Lien désactivé |
|---|---|
| `routers/lots.py::_lot_rattache` | refusé (`ul.actif`) |
| `routers/acces/resident.py::creer_commande` | **accepté** |

Un ancien occupant, dont le rattachement au lot avait été désactivé, pouvait
donc encore **commander un badge Vigik ou une télécommande** pour ce lot. Le
refus existait à dix lignes de là, dans un autre fichier.

La docstring de `_lot_rattache` disait déjà pourquoi : « une règle d'accès en
deux exemplaires ne diverge pas sur le cas nominal : elle diverge le jour où
l'un des deux apprend quelque chose ». Elle a été écrite en généralisant un
défaut passé — et le second exemplaire existait déjà, ailleurs, au moment où
elle a été écrite.

## Pourquoi un accès dupliqué ne se signale jamais

Un accès donné à trop de monde **ne fait aucun bruit** : personne ne se plaint
de pouvoir faire quelque chose. Le seul moment où on l'apprend est celui où
quelqu'un s'en sert. C'est le même raisonnement que
`test_regle_acces_source_unique.py` et `test_destinataires_source_unique.py`.

## Ce que le contrôle vérifie

1. La fonction centrale existe, et elle **exige `actif`**. Un contrôle de source
   unique qui laisserait la source se relâcher ne protégerait plus rien : il
   garantirait seulement que tout le monde se trompe au même endroit.
2. Aucune fonction qui **décide** — qui lève une `HTTPException` — ne lit
   `UserLot` pour son propre compte, hors des exceptions ci-dessous.

⚠️ Le contrôle ne cherche **pas** tous les `select(UserLot)` du projet : il y en
a dix-sept, et la plupart listent ou réparent des liens sans rien autoriser
(appariement, import, écran d'administration). Interdire la lecture aurait
demandé quinze exceptions, c'est-à-dire un contrôle que l'on contourne par
habitude. Ce qui se recopie ici, c'est la **décision d'accès**, et c'est elle qui
est tenue.
"""
from __future__ import annotations

import ast
import pathlib

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Où la question s'écrit, et le nom qu'elle porte.
SOURCE = ("auth/deps.py", "est_rattache_au_lot")

#: Les fonctions qui lisent `UserLot` en levant une `HTTPException`, **sans**
#: décider d'une appartenance — elles **gèrent** les liens eux-mêmes, ce qui est
#: l'inverse : elles ne se demandent pas si un lot est le leur, elles rattachent
#: ou détachent pour le compte d'un autre.
#:
#: Chacune est une route d'administration, donc déjà derrière `require_admin` ou
#: `require_cs_or_admin`. Elles sont nommées **une par une** : le jour où l'une
#: d'elles disparaît ou cesse de lire `UserLot`, ce test échoue et l'exception se
#: retire. Une exception qui survit à son motif finit par couvrir autre chose.
EXCEPTIONS = {
    ("routers/admin/utilisateurs.py", "supprimer_utilisateur"):
        "détache les liens d'un compte supprimé — l'exception porte sur la "
        "suppression, pas sur une appartenance",
    ("routers/lots_imports.py", "resoudre_import"):
        "crée et retire les liens d'un import de lots — c'est elle qui décide "
        "quels rattachements existent",
    ("routers/admin/comptes.py", "traiter_compte"):
        "recopie les rattachements d'un compte aidé vers celui qu'il aide, en "
        "ne lisant que les liens actifs — elle fabrique l'appartenance, elle ne "
        "s'y fie pas",
}


def _fonctions_decidant_sur_userlot():
    """(fichier, fonction) pour chaque fonction qui lit `UserLot` ET lève."""
    for fichier in sorted(_APP.rglob("*.py")):
        source = fichier.read_text(encoding="utf-8")
        if "UserLot" not in source:
            continue
        for noeud in ast.walk(ast.parse(source)):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            corps = ast.unparse(noeud)
            if "select(UserLot)" in corps and "HTTPException" in corps:
                yield fichier.relative_to(_APP).as_posix(), noeud.name, corps


def test_le_controle_voit_bien_quelque_chose():
    """Cas zéro de la portée : une liste vide se lirait comme un succès."""
    vues = list(_fonctions_decidant_sur_userlot())
    assert vues, (
        "aucune fonction lisant UserLot n'a été trouvée — le contrôle a perdu sa "
        "portée (rangement de fichiers, renommage du modèle) et ne vérifie plus rien"
    )
    fichier, fonction = SOURCE
    assert (_APP / fichier).exists(), f"{fichier} a disparu"


def test_la_source_unique_exige_le_lien_ACTIF():
    """Une source unique relâchée fait se tromper tout le monde au même endroit."""
    fichier, fonction = SOURCE
    arbre = ast.parse((_APP / fichier).read_text(encoding="utf-8"))
    corps = {
        n.name: ast.unparse(n)
        for n in ast.walk(arbre)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert fonction in corps, (
        f"`{fonction}` a disparu de {fichier} : la question « ce lot est-il le "
        "mien ? » n'a plus de source unique"
    )
    assert "actif" in corps[fonction], (
        f"`{fonction}` ne regarde plus `actif` : un rattachement désactivé "
        "redonnerait accès au lot — c'est le défaut de #1028, à sa source."
    )


def test_aucune_decision_d_acces_ne_relit_UserLot_elle_meme():
    """Le défaut exact : `creer_commande` interrogeait `UserLot` sans `actif`."""
    fichier_source, nom_source = SOURCE
    fautes = []
    for fichier, fonction, corps in _fonctions_decidant_sur_userlot():
        if fichier == fichier_source:
            continue
        if (fichier, fonction) in EXCEPTIONS:
            continue
        fautes.append(f"  {fichier}::{fonction}")

    assert not fautes, (
        "Ces fonctions décident d'un accès en interrogeant `UserLot` pour leur "
        "propre compte :\n" + "\n".join(fautes) + "\n\n"
        f"La question s'écrit dans `{fichier_source}::{nom_source}`, qui exige le "
        "lien ACTIF. Une seconde écriture ne diverge pas le premier jour — elle "
        "diverge le jour où l'une des deux apprend quelque chose."
    )


def test_aucune_exception_ne_survit_a_son_motif():
    """Une exception qui ne sert plus finit par couvrir autre chose."""
    vues = {(f, n) for f, n, _ in _fonctions_decidant_sur_userlot()}
    perimees = [f"  {f}::{n} — « {raison} »" for (f, n), raison in EXCEPTIONS.items()
                if (f, n) not in vues]
    assert not perimees, (
        "Ces exceptions ne correspondent plus à rien : la fonction a disparu, a "
        "été renommée, ou ne lit plus `UserLot`.\n" + "\n".join(perimees)
        + "\n\nLes retirer de EXCEPTIONS."
    )
