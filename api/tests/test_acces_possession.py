"""Qui détient un accès, et où il se trouve physiquement — `utils/acces_possession` (#1569).

Deux règles de DOMAINE (#779, #1194), prises par les deux chaînes d'import et par
l'appariement automatique ; le module n'était nommé par aucun test. Elles décident
du détenteur affiché ET enregistré : un écart entre les deux se lit par un badge
« chez le propriétaire » alors qu'il est dans la poche du locataire.

Pures : une ligne d'import n'est ici qu'un objet portant ses trois champs.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.utils.acces_possession import chez_le_locataire, possesseur
from tests.aides_badges import TYPES


def _imp(*, chez_locataire: bool, proprietaire=None, locataire=None):
    return SimpleNamespace(
        chez_locataire=chez_locataire,
        user_proprietaire_id=proprietaire,
        user_locataire_id=locataire,
    )


def test_remis_au_locataire_c_est_le_locataire_qui_detient():
    assert possesseur(_imp(chez_locataire=True, proprietaire=1, locataire=2)) == 2


def test_chez_le_proprietaire_c_est_le_proprietaire_qui_detient():
    assert possesseur(_imp(chez_locataire=False, proprietaire=1, locataire=2)) == 1


def test_remis_a_un_locataire_sans_compte_personne_de_connu_ne_detient():
    """Le propriétaire n'est PAS nommé à sa place : ce serait dire l'objet là où il n'est pas."""
    assert possesseur(_imp(chez_locataire=True, proprietaire=1, locataire=None)) is None


def test_chez_le_proprietaire_sans_compte_personne_de_connu_ne_detient():
    assert possesseur(_imp(chez_locataire=False, proprietaire=None, locataire=2)) is None


@pytest.mark.parametrize("valeur,attendu", [(True, True), (False, False), (None, False), (1, True)])
def test_la_possession_physique_est_un_booleen(valeur, attendu):
    assert chez_le_locataire(_imp(chez_locataire=valeur)) is attendu


def test_un_locataire_non_lie_n_empeche_pas_la_possession_chez_lui():
    """La condition « et un locataire LIÉ » est tombée (#1194) : le fait physique prime."""
    assert chez_le_locataire(_imp(chez_locataire=True, locataire=None)) is True


@pytest.mark.parametrize("type_acces", TYPES)
def test_les_deux_types_d_import_portent_les_champs_lus(type_acces):
    """Vigik et télécommande exposent ce que les deux règles lisent — sinon `AttributeError`
    au premier import résolu."""
    ligne = type_acces.modele_import(nom_proprietaire="DUPONT Jean", chez_locataire=True)
    ligne.user_locataire_id = 7

    assert possesseur(ligne) == 7
    assert chez_le_locataire(ligne) is True
