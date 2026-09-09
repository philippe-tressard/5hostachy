"""« Bât. A » ne s'écrit qu'à UN endroit (09/09/2026).

## Ce que ce garde-fou empêche

`f"Bât. {batiment.numero}"` était écrit **onze fois**, dans huit fichiers qui ne
se connaissent pas. Rien n'était encore faux : les onze écrivaient la même chose.
C'est ce qui rend la duplication d'un libellé si difficile à voir — elle ne se
manifeste qu'au **premier changement**, et alors sur les écrans qu'on a oubliés.

Le projet l'a déjà vécu trois fois, et chaque fois le défaut a été trouvé par
quelqu'un qui regardait l'écran, jamais par un contrôle :

* l'**étage**, treize écritures — dont une qui rendait un rez-de-chaussée
  invisible sur la fiche remise aux nouveaux arrivants ;
* les **rôles**, « Conseil syndical » en trois formes, dont deux arrivaient dans
  la même boîte aux lettres ;
* le **périmètre**, qualifié par son parent ici et nu ailleurs.

Chacun a désormais son contrôle. Celui-ci est le quatrième, et il est écrit
*avant* la divergence plutôt qu'après.

## 🔴 Les trois écritures LÉGITIMES, et pourquoi elles le sont

Une exception non écrite n'est pas une exception, c'est un oubli qui ressemble à
une décision. Elles sont déclarées ci-dessous avec leur raison — et le test échoue
si l'une d'elles cesse de servir, sinon la liste deviendrait un cimetière.
"""
from __future__ import annotations

import ast
import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Ce qui est cherché : une **f-string** qui écrit « Bât. » juste avant une
#: interpolation. C'est-à-dire le geste de composer le libellé, et lui seul.
#:
#: 🔴 La première version de ce contrôle cherchait le texte `f"Bât. {` dans le
#: fichier, et elle a échoué sur `fiche_arrivant.py` et `perimetres/arbre.py` —
#: deux **docstrings** qui citent la forme pour expliquer qu'elles ne l'emploient
#: PAS. Un garde-fou ne doit pas se déclencher sur le récit de sa propre
#: application (`standards/04` §39), et neutraliser les lignes de commentaire n'y
#: suffisait pas : la prose vit ici dans des docstrings, qui sont des chaînes
#: comme les autres.
#:
#: L'arbre syntaxique tranche sans exception à écrire : une docstring est une
#: `Constant`, jamais une `JoinedStr`.
_AVANT_INTERPOLATION = "Bât. "

#: Chemin → raison. Une entrée qui ne sert plus fait ÉCHOUER ce test.
EXCEPTIONS = {
    "utils/batiments.py": (
        "la forme elle-même, et le module qui la rend — c'est la source."
    ),
    "seed/patrimoine.py": (
        "l'arbre des périmètres nomme ses nœuds « Bât. {id} », pas « {numero} ». "
        "La divergence est DÉCLARÉE dans ce fichier depuis sa création et "
        "appartient à l'utilisateur : « Bât. A serait plus juste — mais ce serait "
        "un changement ». L'unifier ici changerait tous les badges de périmètre "
        "de la copropriété sans que personne l'ait demandé."
    ),
    "utils/perimetres/libelles.py": (
        "repli d'AFFICHAGE pour un contenu qui cite un nœud supprimé depuis : il "
        "reconstruit « Bât. N » à partir du code `bat:N`, jamais d'un objet "
        "`Batiment`. Ce n'est pas le même point de départ, donc pas la même "
        "fonction."
    ),
}


def _fichiers():
    return [p for p in RACINE.rglob("*.py") if "__pycache__" not in p.parts]


def compose_le_libelle(source: str) -> bool:
    """Une f-string écrit-elle « Bât. » juste avant une interpolation ?

    Ni les commentaires, ni les docstrings, ni les exemples ne peuvent déclencher
    ce contrôle : ce sont des chaînes constantes, et seule une `JoinedStr` — une
    f-string — est regardée.
    """
    for n in ast.walk(ast.parse(source)):
        if not isinstance(n, ast.JoinedStr):
            continue
        for morceau, suivant in zip(n.values, n.values[1:]):
            est_litteral = isinstance(morceau, ast.Constant) and isinstance(
                morceau.value, str
            )
            if (
                est_litteral
                and morceau.value.endswith(_AVANT_INTERPOLATION)
                and isinstance(suivant, ast.FormattedValue)
            ):
                return True
    return False


def test_le_libelle_n_est_ecrit_qu_une_fois():
    fautifs = []
    for p in _fichiers():
        rel = p.relative_to(RACINE).as_posix()
        if rel in EXCEPTIONS:
            continue
        if compose_le_libelle(p.read_text(encoding="utf-8")):
            fautifs.append(rel)

    assert not fautifs, (
        "Ces fichiers composent « Bât. … » eux-mêmes : "
        + ", ".join(sorted(fautifs))
        + ". Employer `libelle_batiment` / `libelle_batiment_ou` de "
        "`app.utils.batiments` — un libellé écrit deux fois ne diverge pas "
        "aujourd'hui, il diverge au premier changement, et sur l'écran qu'on a "
        "oublié."
    )


def test_chaque_EXCEPTION_sert_encore():
    """🔴 Une exception qui ne sert plus n'est plus une exception.

    Sans ce test, la liste ci-dessus grossirait sans jamais maigrir, et finirait
    par autoriser des fichiers qui n'écrivent plus rien — c'est-à-dire par
    couvrir la prochaine copie qu'on y ajouterait sans y penser.
    """
    for rel, raison in EXCEPTIONS.items():
        chemin = RACINE / rel
        assert chemin.exists(), f"{rel} n'existe plus : retirer l'exception."
        assert compose_le_libelle(chemin.read_text(encoding="utf-8")), (
            f"{rel} n'écrit plus « Bât. … » : son exception ne sert plus et doit "
            f"être retirée. Raison enregistrée : {raison}"
        )


def test_cas_zero_le_balayage_regarde_bien_quelque_chose():
    """Si l'arborescence ou la forme changent, le contrôle ne mesure plus rien."""
    assert len(_fichiers()) > 50, "le parcours ne décrit plus `app/`."
    assert compose_le_libelle('x = f"Bât. {bat.numero}"'), (
        "la forme fautive n'est plus reconnue."
    )
    assert not compose_le_libelle("x = libelle_batiment(bat)"), (
        "le contrôle crie sur la forme voulue."
    )
    #  🔴 Le cas qui a fait échouer la première version : la prose qui CITE la
    #  forme pour dire qu'elle ne l'emploie pas.
    prose = 'def f():\n    """jamais un f"Bat. {n}" ici."""\n    return 1\n'
    assert not compose_le_libelle(prose.replace("Bat.", "Bât.")), (
        "le contrôle se déclenche sur le récit de sa propre application."
    )
