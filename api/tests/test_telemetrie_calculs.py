"""Garde-fous des calculs de télémétrie (#354, puis #1545).

Les tests de #354 tenaient le décompte des visiteurs DISTINCTS — trois jours du
même visiteur ne font pas trois visiteurs. Ce décompte n'existe plus depuis le
02/10/2026 : l'événement de télémétrie ne porte plus d'identifiant (#1545), et
le tableau de bord ne compte que des vues. Ce qui reste à tenir est là.
"""

from types import SimpleNamespace

from app.utils.telemetrie_calculs import _cumul_par_page, record


def _ligne(page: str, total: int):
    return SimpleNamespace(page=page, total=total)


def test_les_vues_d_une_page_s_additionnent_d_un_jour_a_l_autre():
    """Des vues, contrairement à des personnes distinctes, s'additionnent."""
    lignes = [_ligne("/actualites", 3), _ligne("/tickets", 1), _ligne("/actualites", 2)]
    assert _cumul_par_page(lignes) == {
        "/actualites": {"page": "/actualites", "total": 5},
        "/tickets": {"page": "/tickets", "total": 1},
    }


def test_aucune_colonne_de_personnes_ne_revient():
    """Le cumul ne rend plus de clé `uniques` : l'écran n'a plus rien à y lire."""
    assert set(_cumul_par_page([_ligne("/faq", 1)])["/faq"]) == {"page", "total"}


def test_cumul_vide():
    assert _cumul_par_page([]) == {}


def test_le_record_est_la_periode_la_plus_vue():
    assert record({"2026-09-01": 4, "2026-09-02": 9, "2026-09-03": 7}, "jour") == {
        "jour": "2026-09-02",
        "vues": 9,
    }


def test_a_egalite_le_record_revient_a_la_premiere_periode():
    """Celle qui l'a établi — et un choix stable d'un affichage à l'autre."""
    assert record({"2026-09": 5, "2026-08": 5}, "mois") == {"mois": "2026-08", "vues": 5}


def test_pas_de_record_sans_donnees():
    """Le cas zéro : rien à afficher, et surtout pas « 0 vue » comme une mesure."""
    assert record({}, "jour") is None
