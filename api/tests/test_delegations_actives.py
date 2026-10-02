"""Les délégations ACTIVES d'un aidant — qui compte, et quand (#1569, #1303, #1565).

`utils/delegations_actives` n'était nommé par aucun test. Il porte une condition de
DROIT — l'aidant lit ce que lit la personne qu'il aide — dont la borne de date a
déjà divergé quand elle était écrite trois fois. Ce fichier la tient sur le
comportement : une délégation compte si elle est acceptée, commencée et pas finie.

« Aujourd'hui » est celui de Paris (`horloge.aujourd_hui`, #1565) : les tests
l'épinglent plutôt que de dépendre de l'heure à laquelle ils tournent.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.core import Delegation, StatutDelegation
from app.utils import horloge
from app.utils.delegations_actives import delegations_de_l_aidant
from tests.aides_base import compte

AUJOURDHUI = date(2026, 10, 2)


@pytest.fixture(autouse=True)
def _jour_epingle(monkeypatch):
    monkeypatch.setattr(horloge, "aujourd_hui", lambda: AUJOURDHUI)


@pytest.fixture()
def acteurs(session):
    """Un aidant, deux personnes aidées et le conseil qui a posé les délégations."""
    return {
        nom: compte(session, prefixe=nom, nom=nom.capitalize())
        for nom in ("aidant", "mandant", "autre", "conseil")
    }


def _deleguer(session, acteurs, *, mandant="mandant", aidant="aidant", **champs) -> Delegation:
    champs.setdefault("statut", StatutDelegation.active)
    champs.setdefault("date_debut", AUJOURDHUI - timedelta(days=10))
    d = Delegation(
        mandant_id=acteurs[mandant].id,
        aidant_id=acteurs[aidant].id,
        cree_par_id=acteurs["conseil"].id,
        **champs,
    )
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


def _ids(session, acteurs, **kw) -> list[int]:
    return [d.id for d in delegations_de_l_aidant(session, acteurs["aidant"].id, **kw)]


def test_une_delegation_acceptee_et_commencee_sans_fin_est_active(session, acteurs):
    d = _deleguer(session, acteurs)
    assert _ids(session, acteurs) == [d.id]


def test_sans_aucune_delegation_la_liste_est_vide(session, acteurs):
    assert _ids(session, acteurs) == []


@pytest.mark.parametrize(
    "statut",
    [StatutDelegation.en_attente, StatutDelegation.revoquee, StatutDelegation.expiree],
)
def test_seule_la_delegation_acceptee_compte(session, acteurs, statut):
    _deleguer(session, acteurs, statut=statut)
    assert _ids(session, acteurs) == []


def test_une_delegation_pas_encore_commencee_ne_compte_pas(session, acteurs):
    _deleguer(session, acteurs, date_debut=AUJOURDHUI + timedelta(days=1))
    assert _ids(session, acteurs) == []


def test_le_jour_de_debut_la_delegation_compte(session, acteurs):
    d = _deleguer(session, acteurs, date_debut=AUJOURDHUI)
    assert _ids(session, acteurs) == [d.id]


def test_le_jour_de_fin_la_delegation_compte_encore_le_lendemain_non(session, acteurs):
    """La borne de fin est INCLUSE : c'est elle qui divergeait entre les trois copies."""
    d = _deleguer(session, acteurs, date_fin=AUJOURDHUI)
    assert _ids(session, acteurs) == [d.id]

    _deleguer(session, acteurs, mandant="autre", date_fin=AUJOURDHUI - timedelta(days=1))
    assert _ids(session, acteurs) == [d.id], "une délégation finie hier ne doit plus compter"


def test_une_fin_lointaine_compte(session, acteurs):
    d = _deleguer(session, acteurs, date_fin=AUJOURDHUI + timedelta(days=365))
    assert _ids(session, acteurs) == [d.id]


def test_on_ne_lit_que_les_delegations_de_cet_aidant(session, acteurs):
    """Une délégation où l'aidant est le MANDANT n'est pas la sienne à exercer."""
    _deleguer(session, acteurs, mandant="aidant", aidant="mandant")
    assert _ids(session, acteurs) == []
    inverse = [d.id for d in delegations_de_l_aidant(session, acteurs["mandant"].id)]
    assert len(inverse) == 1


def test_le_mandant_filtre_les_delegations(session, acteurs):
    d1 = _deleguer(session, acteurs, mandant="mandant")
    d2 = _deleguer(session, acteurs, mandant="autre")
    assert sorted(_ids(session, acteurs)) == sorted([d1.id, d2.id])
    assert _ids(session, acteurs, mandant_id=acteurs["autre"].id) == [d2.id]
    assert _ids(session, acteurs, mandant_id=acteurs["conseil"].id) == []


def test_le_filtre_de_mandant_n_elargit_rien(session, acteurs):
    """Un mandant dont la délégation est révoquée ne revient pas par le filtre."""
    _deleguer(session, acteurs, statut=StatutDelegation.revoquee)
    assert _ids(session, acteurs, mandant_id=acteurs["mandant"].id) == []


def test_le_jour_est_celui_de_l_horloge_de_paris(session, acteurs, monkeypatch):
    """La condition lit `horloge.aujourd_hui()` (#1565) : changer le jour change le verdict."""
    _deleguer(session, acteurs, date_fin=AUJOURDHUI)
    assert len(_ids(session, acteurs)) == 1
    monkeypatch.setattr(horloge, "aujourd_hui", lambda: AUJOURDHUI + timedelta(days=1))
    assert _ids(session, acteurs) == []
