"""Une requête `text()` dont les dates se comparent comme la base les stocke — `requete_liee` (#1569, #1298).

SQLite stocke un `DateTime` sous la forme `2026-09-25 18:00:00.000000` (une ESPACE
avant l'heure) et compare des CHAÎNES. Un seuil lié tel quel en
`datetime.isoformat()` porte un `T`, qui se classe après l'espace : le jour du seuil,
toute ligne paraissait « antérieure » quelle que soit son heure — la purge du dimanche
effaçait des jetons de session encore valides. Le module n'était nommé par aucun test ;
`test_purge_dates_liees.py` ne tient que les appelants.

Ici, sur une base réelle : le témoin (un seuil non lié se trompe), puis le verdict
correct, puis les paramètres qui ne sont pas des dates.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from sqlalchemy import text

from app.utils.requete_liee import requete_liee
from tests.aides_base import compte

SEUIL = datetime(2026, 9, 25, 12, 0, 0)


def _ids(session, requete) -> set[int]:
    return {r[0] for r in session.execute(requete).all()}


def _comptes_crees_a(session, *heures: datetime) -> list[int]:
    ids = []
    for h in heures:
        u = compte(session, prefixe="rl")
        u.cree_le = h
        session.add(u)
        session.commit()
        ids.append(u.id)
    return ids


@pytest.mark.sqlite_seulement("témoin du bug : SQLite compare des chaînes, PostgreSQL refuse")
def test_temoin_un_seuil_isoformat_se_trompe_le_jour_du_seuil(session):
    """Sans lui, le test suivant ne prouverait rien : c'est l'erreur que le module évite."""
    avant_le_seuil, apres_le_seuil = _comptes_crees_a(
        session, datetime(2026, 9, 25, 8, 0), datetime(2026, 9, 25, 18, 0)
    )

    mal_lie = text("SELECT id FROM utilisateur WHERE cree_le < :s").bindparams(s=SEUIL.isoformat())

    #  Le `T` classe le seuil APRÈS toute ligne du même jour : les deux « précèdent ».
    assert _ids(session, mal_lie) >= {avant_le_seuil, apres_le_seuil}


def test_un_datetime_se_compare_comme_la_base_le_stocke(session):
    avant_le_seuil, apres_le_seuil, la_veille, le_lendemain = _comptes_crees_a(
        session,
        datetime(2026, 9, 25, 8, 0),
        datetime(2026, 9, 25, 18, 0),
        datetime(2026, 9, 24, 23, 59),
        datetime(2026, 9, 26, 0, 1),
    )

    anterieurs = _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE cree_le < :s", s=SEUIL)
    )
    posterieurs = _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE cree_le >= :s", s=SEUIL)
    )

    assert anterieurs == {avant_le_seuil, la_veille}
    assert posterieurs == {apres_le_seuil, le_lendemain}
    assert anterieurs.isdisjoint(posterieurs)


def test_a_l_instant_du_seuil_la_ligne_n_est_pas_anterieure(session):
    [pile] = _comptes_crees_a(session, SEUIL)

    assert pile not in _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE cree_le < :s", s=SEUIL)
    )
    assert pile in _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE cree_le <= :s", s=SEUIL)
    )


def test_les_autres_parametres_sont_lies_tels_quels(session):
    u = compte(session, prefixe="rl")

    trouve = _ids(session, requete_liee("SELECT id FROM utilisateur WHERE id = :i", i=u.id))
    absent = _ids(
        session, requete_liee("SELECT id FROM utilisateur WHERE email = :e", e="nul@exemple.test")
    )

    assert trouve == {u.id}
    assert absent == set()


def test_plusieurs_parametres_se_melangent(session):
    ancien, recent = _comptes_crees_a(session, datetime(2026, 9, 1), datetime(2026, 10, 1))

    ids = _ids(
        session,
        requete_liee(
            "SELECT id FROM utilisateur WHERE cree_le < :s AND id IN (:a, :b)",
            s=SEUIL,
            a=ancien,
            b=recent,
        ),
    )

    assert ids == {ancien}


def test_sans_parametre_la_requete_est_un_text_ordinaire(session):
    requete = requete_liee("SELECT 1")
    assert session.execute(requete).scalar() == 1
