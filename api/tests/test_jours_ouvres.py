"""Les jours ouvrés et les fériés français — `app/utils/jours_ouvres.py` (#1643).

Les délais de la synthèse d'une affaire close (durée, première réponse du
syndic, réaction après une relance) sont opposables en assemblée générale : la
règle se fixe ici, cas zéro compris — clôture un samedi, affaire ouverte et
close le même jour, fin avant le début.
"""

from __future__ import annotations

from datetime import date, datetime

from app.utils.jours_ouvres import (
    au_demi_jour,
    est_ouvre,
    heures_ouvrees,
    jours_feries,
    jours_ouvres,
    libelle_jours,
    paques,
)


def test_paques_sur_des_annees_connues():
    assert paques(2024) == date(2024, 3, 31)
    assert paques(2025) == date(2025, 4, 20)
    assert paques(2026) == date(2026, 4, 5)
    assert paques(2027) == date(2027, 3, 28)


def test_les_onze_feries_de_2026():
    feries = jours_feries(2026)
    assert len(feries) == 11
    for jour in (
        date(2026, 1, 1),
        date(2026, 4, 6),  # lundi de Pâques
        date(2026, 5, 1),
        date(2026, 5, 8),
        date(2026, 5, 14),  # Ascension
        date(2026, 5, 25),  # lundi de Pentecôte
        date(2026, 7, 14),
        date(2026, 8, 15),
        date(2026, 11, 1),
        date(2026, 11, 11),
        date(2026, 12, 25),
    ):
        assert jour in feries, jour
    #  Pas d'Alsace-Moselle : ni Vendredi saint, ni 26 décembre.
    assert date(2026, 4, 3) not in feries
    assert date(2026, 12, 26) not in feries


def test_un_jour_ouvre():
    assert est_ouvre(date(2026, 10, 2))  # vendredi
    assert not est_ouvre(date(2026, 10, 3))  # samedi
    assert not est_ouvre(date(2026, 10, 4))  # dimanche
    assert not est_ouvre(date(2026, 7, 14))  # mardi férié


def test_ouverte_et_close_le_meme_jour():
    """Cas zéro : 10 h → 15 h, cinq heures — 0,625 j, affiché 0,5 j."""
    debut, fin = datetime(2026, 10, 1, 10), datetime(2026, 10, 1, 15)
    assert heures_ouvrees(debut, fin) == 5
    assert jours_ouvres(debut, fin) == 0.5


def test_les_heures_hors_bureau_ne_comptent_pas():
    assert heures_ouvrees(datetime(2026, 10, 1, 6), datetime(2026, 10, 1, 9)) == 0
    assert heures_ouvrees(datetime(2026, 10, 1, 17), datetime(2026, 10, 1, 23)) == 0
    assert heures_ouvrees(datetime(2026, 10, 1, 8), datetime(2026, 10, 1, 18)) == 8


def test_cloture_un_samedi():
    """Cas zéro : vendredi 16 h → samedi midi ne compte que l'heure du vendredi."""
    debut, fin = datetime(2026, 10, 2, 16), datetime(2026, 10, 3, 12)
    assert heures_ouvrees(debut, fin) == 1
    assert jours_ouvres(debut, fin) == 0


def test_le_week_end_et_les_feries_sautent():
    assert jours_ouvres(datetime(2026, 10, 2, 9), datetime(2026, 10, 5, 17)) == 2
    #  Pâques 2026 : vendredi 3 avril, lundi 6 férié, mardi 7.
    assert jours_ouvres(datetime(2026, 4, 3, 9), datetime(2026, 4, 7, 17)) == 2


def test_une_fin_avant_le_debut_ne_rend_pas_de_duree_negative():
    assert heures_ouvrees(datetime(2026, 10, 2, 12), datetime(2026, 10, 1, 12)) == 0


def test_le_demi_jour():
    assert au_demi_jour(2.26) == 2.5
    assert au_demi_jour(2.24) == 2.0
    assert au_demi_jour(0) == 0


def test_le_libelle():
    assert libelle_jours(22.5) == "22,5 j"
    assert libelle_jours(3.0) == "3 j"
    assert libelle_jours(0) == "0 j"
    assert libelle_jours(None) == "—"
