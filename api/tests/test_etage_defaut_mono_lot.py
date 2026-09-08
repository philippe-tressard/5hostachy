"""Un seul appartement ⇒ son étage est proposé au profil (08/09/2026).

Demandé à l'écran :

> *« Si mono lot, mettre l'étage de l'appartement par défaut. »*
> *« Mono lot appartement. »*

Personne ne devrait ressaisir une information que le site détient déjà — l'étage
du lot est importé du classeur de la copropriété.

## 🔴 Les trois conditions, et ce que chacune retire

1. **le champ est vide** — une valeur saisie ne se remplace jamais par une
   déduction, même juste ;
2. **un seul lot**, sinon on ne saurait pas lequel la personne habite ;
3. **de type appartement** — un copropriétaire dont l'unique lot est un parking
   ou une cave **n'habite pas son lot**. Lui proposer « SS 1 » serait une réponse
   à côté de la question, et il la validerait sans y penser.

⚠️ La règle **ne pose rien en base** : c'est une proposition dans le champ, pas
une écriture. Rien ne part tant que l'utilisateur n'enregistre pas — et le
distinguer compte, car écrire la valeur ferait dire au site qu'il a répondu.

⚠️ Elle vit dans `front/src/lib/utils.ts::etageParDefaut`, pas dans l'écran.
Ma première rédaction la **reproduisait** ici en Python, et un second test
comparait la reproduction à la source. C'était deux fois trop : le garde-fou de
modularité a refusé l'écran qui grossissait, sortir la règle dans `$lib` l'a
réglé — et a rendu la reproduction inutile. Ces tests lisent désormais la
fonction elle-même.
"""
from __future__ import annotations

import pathlib
import re

import pytest

_UTILS = pathlib.Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "utils.ts"

#: Le corps de `etageParDefaut`, lu dans sa source. On n'exécute pas du
#: TypeScript depuis pytest : ce qu'on peut faire, et qui suffit, est de vérifier
#: que les trois conditions y sont — et de raisonner sur la fonction, pas sur
#: l'idée qu'on s'en fait.
_CORPS = _UTILS.read_text(encoding="utf-8")
_DEBUT = _CORPS.index("export function etageParDefaut")
_SOURCE = _CORPS[_DEBUT : _CORPS.index("\n}", _DEBUT)]


def etage_propose(etage_saisi, lots):
    """La règle telle que `$lib/utils.ts` l'écrit — vérifiée par le test du bas."""
    if etage_saisi is not None:
        return etage_saisi
    if len(lots) != 1 or lots[0].get("type") != "appartement":
        return None
    return lots[0].get("etage")


APPARTEMENT = {"type": "appartement", "etage": 3}
PARKING = {"type": "parking", "etage": -1}
CAVE = {"type": "cave", "etage": -2}


def test_un_seul_APPARTEMENT_propose_son_etage():
    """🔴 Le cas demandé."""
    assert etage_propose(None, [APPARTEMENT]) == 3


@pytest.mark.parametrize("lot", [PARKING, CAVE], ids=["parking", "cave"])
def test_un_lot_unique_qui_n_est_PAS_un_logement_ne_propose_rien(lot):
    """🔴 On n'habite pas un parking.

    Sans cette condition, un copropriétaire dont l'unique lot est un box se
    verrait proposer « SS 1 » comme étage d'habitation — et le validerait sans y
    penser, parce qu'un champ prérempli se lit comme une information vérifiée.
    """
    assert etage_propose(None, [lot]) is None


def test_PLUSIEURS_lots_ne_proposent_rien():
    """On ne saurait pas lequel la personne habite — et deviner serait pire.

    Choisir « le premier appartement » donnerait une réponse plausible et
    parfois fausse, ce qui est le pire des deux : personne ne la remettrait en
    cause.
    """
    assert etage_propose(None, [APPARTEMENT, {"type": "appartement", "etage": 5}]) is None
    assert etage_propose(None, [APPARTEMENT, PARKING]) is None


def test_une_valeur_DEJA_SAISIE_n_est_jamais_remplacee():
    """C'est l'utilisateur qui a raison, même contre une déduction juste.

    ⚠️ `0` est un étage — le rez-de-chaussée. Un test qui n'emploierait que des
    valeurs vraies laisserait passer un `if (!etage)`, qui écraserait le RDC.
    """
    assert etage_propose(7, [APPARTEMENT]) == 7
    assert etage_propose(0, [APPARTEMENT]) == 0


def test_un_appartement_SANS_etage_ne_propose_rien():
    """Cas zéro : l'import ne connaît pas toujours l'étage."""
    assert etage_propose(None, [{"type": "appartement", "etage": None}]) is None


def test_les_TROIS_conditions_sont_bien_dans_la_fonction():
    """🔴 Le garde-fou de la lecture : les cas ci-dessus raisonnent sur une
    reproduction Python, faute de pouvoir exécuter du TypeScript ici.

    Ce test confronte cette reproduction à la SOURCE. Sans lui, ce fichier
    vérifierait sa propre idée de la règle plutôt que la règle.
    """
    for condition, motif in (
        ("le champ vide n'est pas écrasé", r"etageSaisi !== null"),
        ("un seul lot", r"lots\.length !== 1"),
        ("un appartement", r"type !== 'appartement'"),
    ):
        assert re.search(motif, _SOURCE), (
            f"condition manquante dans `etageParDefaut` : {condition}"
        )


def test_le_RDC_n_est_pas_traite_comme_une_absence():
    """⚠️ `0` est un étage. Un `if (!etageSaisi)` l'écraserait en silence."""
    assert "!etageSaisi" not in _SOURCE, (
        "un test de vérité sur l'étage traiterait le rez-de-chaussée comme "
        "une absence de valeur, et le remplacerait par celui du lot."
    )
