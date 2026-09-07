"""Ancienneté annoncée dans la relance syndic (01/08/2026).

Le préambule affirme au gestionnaire depuis combien de temps ses dossiers
n'avancent plus. Une formule fausse — « plus de 1 mois », « 3 à 3 mois », ou
« plus d'un mois » pour un ticket en souffrance depuis cinq — décrédibiliserait
tout le courrier, et c'est exactement ce que le CS y cherche : un fait qui se
conteste mal. D'où ces tests sur une fonction pure.
"""
from datetime import datetime

import pytest

from app.utils.dates_fr import formule_anciennete, mois_ecoules

_MAINTENANT = datetime(2026, 8, 1, 12, 0)


@pytest.mark.parametrize(
    "depuis,attendu",
    [
        (datetime(2026, 7, 25, 12, 0), 0),   # une semaine
        (datetime(2026, 7, 1, 12, 0), 1),    # un mois pile
        (datetime(2026, 7, 2, 12, 0), 0),    # un jour de moins qu'un mois
        (datetime(2026, 3, 1, 12, 0), 5),
        (datetime(2025, 8, 1, 12, 0), 12),
    ],
)
def test_mois_ecoules(depuis, attendu):
    assert mois_ecoules(depuis, _MAINTENANT) == attendu


def test_mois_ecoules_compte_des_mois_calendaires():
    """31/01 → 28/02 fait bien un mois, ce qu'une division par 30 jours nierait."""
    assert mois_ecoules(datetime(2026, 1, 31), datetime(2026, 2, 28)) == 0
    assert mois_ecoules(datetime(2026, 1, 28), datetime(2026, 2, 28)) == 1


@pytest.mark.parametrize(
    "mois,attendu",
    [
        ([], "plus d'un mois"),
        ([0], "plus d'un mois"),
        ([1], "plus d'un mois"),          # jamais « plus de 1 mois »
        ([4], "plus de 4 mois"),
        ([3, 3], "plus de 3 mois"),       # jamais « 3 à 3 mois »
        ([1, 5], "un à 5 mois"),
        ([2, 7], "2 à 7 mois"),
        ([0, 4], "un à 4 mois"),
    ],
)
def test_formule_anciennete(mois, attendu):
    assert formule_anciennete(mois) == attendu
