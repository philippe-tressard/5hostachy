"""« Vouliez-vous TK-E00066 ? » — un numéro d'affaire mal tapé (05/10/2026).

Le transfert du 05/10 portait `TK-E000066` pour `TK-E00066`. La proposition ne
se fait qu'à UN candidat, et ne rattache jamais rien.
"""

from __future__ import annotations

from app.utils.courriel_numero import a_une_faute_pres, voisins


def test_un_zero_de_trop_est_une_faute_pres():
    assert a_une_faute_pres("tk-e000066", "tk-e00066")
    assert a_une_faute_pres("tk-e00066", "tk-e000066")


def test_un_chiffre_change_est_une_faute_pres_mais_deux_non():
    assert a_une_faute_pres("tk-109008", "tk-109009")
    assert not a_une_faute_pres("tk-109008", "tk-109099")


def test_le_meme_numero_n_est_pas_son_propre_voisin():
    assert not a_une_faute_pres("tk-109008", "tk-109008")


def test_les_longueurs_trop_differentes_ne_sont_pas_voisines():
    assert not a_une_faute_pres("tk-1090", "tk-109008")


def test_la_casse_ne_compte_pas():
    assert voisins("TK-E000066", ["tk-e00066", "TK-A00017"]) == ["tk-e00066"]


def test_plusieurs_candidats_se_voient_tous():
    # Deux affaires à une faute : l'aide se tait (voir `aide_au_numero`).
    assert len(voisins("TK-E00060", ["TK-E00061", "TK-E00062", "TK-A00017"])) == 2
