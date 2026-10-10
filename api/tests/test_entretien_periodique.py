"""Espace CS › Reporting › « Entretien périodique » (arbitré le 10/10/2026).

Deux demandes, une seule règle (`utils/entretien_periodique`) :

1. la **relance syndic** n'écarte plus que les entretiens PÉRIODIQUES — sous
   contrat ou à récurrence ; un Entretien ouvert à la main y reste
   (`test_relance_syndic_affaires_suivies` tient ce sens-là) ;
2. la vue **Entretien périodique** les montre, une ligne par visite de l'année
   civile, avec son état : réalisée, non réalisée, à venir, à planifier, annulée.

Les visites converties du calendrier n'avaient pas de contrat : la migration
0273 le leur rend, sans quoi la règle n'en reconnaissait aucune en production.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.models.core import Ticket
from app.models.evenement import Evenement
from app.models.prestataires import ContratEntretien, Prestataire
from app.routers.tickets.entretien_periodique import lister_entretiens_periodiques
from app.utils import horloge
from tests.aides_base import compte
from tests.aides_migrations import charger_migration

#: Le jour de la lecture : le 10 octobre 2026, midi à Paris.
AUJOURD_HUI = datetime(2026, 10, 10, 10, 0, 0)


@pytest.fixture()
def conseil(session, monkeypatch):
    monkeypatch.setattr(horloge, "maintenant", lambda: AUJOURD_HUI)
    return compte(session, roles_json="conseil_syndical")


def _affaire(session, auteur, numero: str, **champs) -> Ticket:
    valeurs = {"titre": numero, "categorie": "entretien", "statut": "chez_prestataire", **champs}
    t = Ticket(numero=numero, description="d", auteur_id=auteur.id, **valeurs)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _lire(session, conseil):
    return lister_entretiens_periodiques(session=session, _user=conseil)


def test_chaque_visite_de_l_exercice_porte_son_etat(session, conseil):
    prest = Prestataire(nom="DURAND", specialite="Toiture")
    session.add(prest)
    session.commit()
    contrat = ContratEntretien(
        copropriete_id=1, prestataire_id=prest.id, libelle="Entretien toitures"
    )
    session.add(contrat)
    session.commit()
    sous_contrat = {"contrat_id": contrat.id, "prestataire_id": prest.id}
    _affaire(
        session,
        conseil,
        "TK-JANV",
        debut=datetime(2026, 1, 15),
        statut="résolu",
        ferme_le=datetime(2026, 1, 20),
        **sous_contrat,
    )
    _affaire(session, conseil, "TK-JUIL", debut=datetime(2026, 7, 15), **sous_contrat)
    _affaire(session, conseil, "TK-DEC", debut=datetime(2026, 12, 1), **sous_contrat)
    _affaire(
        session,
        conseil,
        "TK-SANS-DATE",
        frequence_type="mois",
        frequence_valeur=6,
        cree_le=AUJOURD_HUI,
    )
    _affaire(
        session,
        conseil,
        "TK-ANNULEE",
        debut=datetime(2026, 3, 1),
        statut="annulé",
        frequence_type="mois",
        frequence_valeur=6,
    )

    reponse = _lire(session, conseil)

    assert reponse.exercice == 2026
    etats = {v.numero: v.etat for v in reponse.visites}
    assert etats == {
        "TK-JANV": "realisee",
        "TK-ANNULEE": "annulee",
        "TK-JUIL": "non_realisee",
        "TK-SANS-DATE": "a_planifier",
        "TK-DEC": "a_venir",
    }
    juillet = next(v for v in reponse.visites if v.numero == "TK-JUIL")
    assert (juillet.prestataire_nom, juillet.contrat_libelle) == (
        "DURAND",
        "Entretien toitures",
    )
    #  L'ordre des dates : la visite sans date se range à sa création (aujourd'hui).
    assert [v.numero for v in reponse.visites] == [
        "TK-JANV",
        "TK-ANNULEE",
        "TK-JUIL",
        "TK-SANS-DATE",
        "TK-DEC",
    ]


def test_la_visite_du_jour_est_a_venir_et_non_en_retard(session, conseil):
    #  22 h UTC le 9 = minuit le 10 à Paris : le jour de la visite est aujourd'hui.
    _affaire(session, conseil, "TK-JOUR", debut=datetime(2026, 10, 9, 22, 0), contrat_id=1)
    assert [v.etat for v in _lire(session, conseil).visites] == ["a_venir"]


@pytest.mark.parametrize(
    "champs",
    [
        pytest.param({}, id="entretien-ponctuel"),
        pytest.param({"categorie": "panne", "contrat_id": 1}, id="autre-categorie"),
        pytest.param({"contrat_id": 1, "debut": datetime(2025, 7, 15)}, id="exercice-passe"),
        pytest.param({"contrat_id": 1, "archive_manuel": True}, id="archivee"),
        pytest.param({"contrat_id": 1, "fusionnee_dans_id": -1}, id="absorbee"),
    ],
)
def test_ce_qui_n_est_pas_une_visite_de_l_exercice(session, conseil, champs):
    _affaire(session, conseil, "TK-X", **{"debut": datetime(2026, 7, 15), **champs})
    assert _lire(session, conseil).visites == []


# ── La migration 0273 ───────────────────────────────────────────────────────


def _evenement(session, auteur, type_: str) -> Evenement:
    e = Evenement(titre="e", type=type_, debut=datetime(2026, 7, 15), auteur_id=auteur.id)
    session.add(e)
    session.commit()
    session.refresh(e)
    return e


def test_la_migration_rend_leur_contrat_aux_visites_du_calendrier(session, conseil, monkeypatch):
    migration = charger_migration("0273")
    contrats = []
    for prestataire_id, libelle, frequence in (
        (4, "Entretien toitures", "fois_par_an"),
        (4, "Gouttières", "fois_par_an"),
        (11, "Porte de parking", "fois_par_an"),
        (12, "Sans rythme", None),
    ):
        c = ContratEntretien(
            copropriete_id=1,
            prestataire_id=prestataire_id,
            libelle=libelle,
            frequence_type=frequence,
            frequence_valeur=2 if frequence else None,
        )
        session.add(c)
        contrats.append(c)
    session.commit()
    recurrent = _evenement(session, conseil, "maintenance_recurrente").id
    ponctuel = _evenement(session, conseil, "maintenance").id
    cas = {
        #  Le titre nomme le contrat parmi deux du même prestataire.
        "par-titre": {"prestataire_id": 4, "titre": "Toitures — Entretien toitures"},
        #  Un seul contrat en cours : il est retenu sans que le titre le nomme.
        "seul": {"prestataire_id": 11, "titre": "Maintenance porte"},
        #  Deux contrats, aucun nommé : pas de devinette.
        "ambigu": {"prestataire_id": 4, "titre": "Visite"},
        #  Un contrat sans fréquence laisserait la visite sans rythme.
        "sans-rythme": {"prestataire_id": 12, "titre": "Sans rythme"},
    }
    tickets = {
        nom: _affaire(session, conseil, f"TK-{nom}", promu_depuis_evenement_id=recurrent, **c)
        for nom, c in cas.items()
    }
    tickets["ponctuel"] = _affaire(
        session, conseil, "TK-ponctuel", prestataire_id=11, promu_depuis_evenement_id=ponctuel
    )

    monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=session.connection))
    migration.upgrade()
    migration.upgrade()  # idempotente
    session.expire_all()

    rattaches = {nom: session.get(Ticket, t.id).contrat_id for nom, t in tickets.items()}
    assert rattaches == {
        "par-titre": contrats[0].id,
        "seul": contrats[2].id,
        "ambigu": None,
        "sans-rythme": None,
        "ponctuel": None,
    }
