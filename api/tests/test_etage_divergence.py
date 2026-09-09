"""Le logement de référence, l'étage effectif et la divergence (09/09/2026).

## Pourquoi ces trois fonctions ont un test à elles

La règle « proposer l'étage du lot quand il n'y en a qu'un » a déjà vécu une
fois : elle s'appelait `etageParDefaut`, côté front, écrite le 08/09/2026 avec
son test — et supprimée le lendemain avec lui, quand le champ qui l'employait a
quitté le profil. Elle a été redemandée le soir même.

Ce n'est pas la suppression qui était fautive (une règle sans appelant ne se
garde pas), c'est que rien ne disait ce que le produit y perdait. Ces tests-ci
décrivent la règle par ses CAS LIMITES, ceux dont chacun retire une réponse
plausible et fausse : c'est ce qui survit à un déplacement de champ.

⚠️ Aucune base, aucun SMTP : ces fonctions sont pures. L'envoi du courriel, lui,
est une conséquence — il se vérifie par la condition qui le déclenche, dans
`routers/auth_profil.py`, et non en observant un message parti.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.utils.etages import divergence_etage, etage_effectif, logement_de_reference


@dataclass
class LotFactice:
    type: str = "appartement"
    etage: int | None = 2
    id: int = 1


def test_un_logement_unique_avec_etage_est_la_reference():
    assert logement_de_reference([LotFactice(etage=3)]).etage == 3


def test_DEUX_logements_ne_designent_rien():
    """On ne saurait pas lequel il habite — et « le premier » serait plausible."""
    assert logement_de_reference([LotFactice(id=1), LotFactice(id=2, etage=5)]) is None


@pytest.mark.parametrize("type_de_lot", ["cave", "parking", "commerce"])
def test_un_lot_qui_n_est_PAS_un_logement_ne_designe_rien(type_de_lot):
    """Un copropriétaire dont l'unique lot est un parking n'habite pas son lot."""
    assert logement_de_reference([LotFactice(type=type_de_lot, etage=-1)]) is None


def test_un_logement_SANS_etage_ne_designe_rien():
    """Il n'apprend rien, et le comparer inventerait une divergence."""
    assert logement_de_reference([LotFactice(etage=None)]) is None


def test_le_rez_de_chaussee_est_un_etage():
    """🔴 `0` est faux en Python : un test de vérité effacerait le RDC.

    C'est le défaut qui avait privé d'étage les conseillers du rez-de-chaussée
    sur la fiche remise aux arrivants (#844) — pas un étage faux, un étage
    ABSENT, et seulement pour ceux dont l'information est la plus simple.
    """
    assert logement_de_reference([LotFactice(etage=0)]).etage == 0
    assert etage_effectif(4, [LotFactice(etage=0)]) == 0
    assert divergence_etage(0, [LotFactice(etage=2)]) == (0, 2)


def test_le_lot_l_emporte_sur_la_saisie():
    assert etage_effectif(4, [LotFactice(etage=2)]) == 2


def test_sans_lot_la_saisie_prend_le_relais():
    """Le cas qui a fait redemander le champ : un compte sans aucun lot."""
    assert etage_effectif(4, []) == 4


def test_deux_valeurs_egales_ne_divergent_pas():
    assert divergence_etage(2, [LotFactice(etage=2)]) is None


def test_une_saisie_ABSENTE_n_est_pas_une_divergence():
    """Ne rien dire n'est pas dire le contraire — sinon l'administrateur serait
    prévenu pour chaque compte qui n'a pas rempli un champ facultatif."""
    assert divergence_etage(None, [LotFactice(etage=2)]) is None
