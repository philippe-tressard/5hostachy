"""`couvre()` — un périmètre en englobe-t-il un autre ?

C'est la question d'un **filtre**, et elle a un sens : une portée large englobe
une portée étroite, jamais l'inverse. Confondre les deux sens ferait tout
apparaître partout, ce qui est la façon la plus discrète de rendre un filtre
inutile.

## Pourquoi ce test existe (10/09/2026)

Le carnet d'entretien filtrait d'abord sur `batiment_id`. Deux défauts en
découlaient, tous deux signalés à l'écran :

1. choisir un bâtiment **vidait** le carnet — tout ce qui portait `NULL`, c'est-à-dire
   ce qui couvre la résidence entière, était exclu ;
2. on ne pouvait pas filtrer sur « Parking » ou « Caves », qui ne sont pas des
   bâtiments — alors que l'arborescence administrée, elle, les connaît.

`couvre()` répond aux deux, et ce test fixe les trois façons d'entrer dans un
périmètre **et le sens qui doit rester fermé**.

⚠️ L'arbre est injecté : ces règles ne dépendent d'aucune base, et un test qui
aurait besoin de la production pour s'exécuter ne s'exécuterait jamais.
"""
from __future__ import annotations

import pytest

import importlib

from app.utils.perimetres.arbre import Noeud, couvre

#  ⚠️ `import app.utils.perimetres.arbre as m` ne rend PAS le module : le paquet
#  réexporte une FONCTION `arbre`, qui masque le sous-module homonyme.
module_arbre = importlib.import_module('app.utils.perimetres.arbre')


def _noeud(code, parent=None, globale=False, batiment=None) -> Noeud:
    return Noeud(
        code=code,
        libelle=code,
        libelle_court=code,
        description="",
        icone=None,
        parent=parent,
        batiment_id=batiment,
        portee_globale=globale,
        selectionnable=True,
        actif=True,
        ordre=0,
    )


#: Une copropriété plausible : une racine globale, un regroupement de bâtiments,
#: un espace sous l'un d'eux, et deux espaces transverses qui n'ont AUCUN
#: bâtiment — ce sont eux que l'ancien filtre ne savait pas nommer.
ARBRE = {
    "résidence": _noeud("résidence", globale=True),
    "bâtiments": _noeud("bâtiments"),
    "bat:3": _noeud("bat:3", parent="bâtiments", batiment=3),
    "bat:3:toit": _noeud("bat:3:toit", parent="bat:3", batiment=None),
    "parking": _noeud("parking"),
    "caves": _noeud("caves"),
}


@pytest.fixture(autouse=True)
def _arbre_injecte(monkeypatch):
    monkeypatch.setattr(module_arbre, "arbre", lambda: ARBRE)


def test_sans_filtre_tout_passe():
    """L'appelant n'a pas à traiter « pas de filtre » à part."""
    assert couvre(["bat:3"], None) is True


def test_le_meme_code_passe():
    assert couvre(["parking"], "parking") is True


def test_un_ANCETRE_du_demande_passe():
    """« Bât. 3 » couvre « Bât. 3 › Toit » : le toit fait partie du bâtiment."""
    assert couvre(["bat:3"], "bat:3:toit") is True


def test_une_PORTEE_GLOBALE_passe_partout():
    """🔴 Le défaut du 10/09/2026 : un contrat de nettoyage qui couvre toute la
    résidence entretient AUSSI le parking. L'exclure d'un filtre « Parking »
    vidait le carnet."""
    assert couvre(["résidence"], "parking") is True
    assert couvre(["résidence"], "bat:3") is True


def test_une_portee_ETROITE_ne_passe_PAS():
    """🔴 Le sens qui doit rester fermé.

    Un contrat sur le bâtiment 3 n'entre pas dans un filtre « Parking ». Si les
    deux sens passaient, tout apparaîtrait partout — un filtre qui ne filtre
    rien, et personne ne le remarquerait.
    """
    assert couvre(["bat:3"], "parking") is False
    assert couvre(["parking"], "caves") is False


def test_un_DESCENDANT_du_demande_ne_passe_pas():
    """Le toit du bâtiment 3 n'est pas tout le bâtiment 3."""
    assert couvre(["bat:3:toit"], "bat:3") is False


def test_rien_de_declare_couvre_tout():
    """Ne rien déclarer, c'est ne rien restreindre — ce que valait
    implicitement `batiment_id IS NULL` avant que les contrats aient un périmètre."""
    assert couvre([], "parking") is True


def test_un_code_INCONNU_ne_fait_pas_lever():
    """Un contenu qui cite un périmètre supprimé ne compte pas — il ne fait pas
    échouer la requête pour autant."""
    assert couvre(["periletre-supprime"], "parking") is False


def test_l_arbre_VIDE_ne_filtre_rien(monkeypatch):
    """`standards/04` : une mesure impossible ne rend pas un verdict.

    Arbre illisible = on ne peut rien décider. Tout masquer ferait lire un carnet
    vide comme une absence de données ; ne rien filtrer se voit tout de suite.
    """
    monkeypatch.setattr(module_arbre, "arbre", dict)
    assert couvre(["bat:3"], "parking") is True
