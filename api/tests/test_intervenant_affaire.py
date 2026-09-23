"""L'intervenant, la récurrence d'un Entretien, et les catégories du conseil (#1092, lot 5).

Arbitrages de l'utilisateur, 23/09/2026 :

- la section « Intervenant » est construite — le conseil y désigne le
  prestataire ; la récurrence (« tous les N mois ») ne vaut que pour la
  catégorie **Entretien**, née pour recevoir les maintenances du calendrier ;
- **Étude & travaux** et **Entretien** sont réservées au conseil, comme
  Actualité ;
- le suivi gagne deux états, **À l'AG** et **Chez le prestataire** — les deux
  colonnes du kanban qu'aucun état ne disait.

Les règles vivent dans `utils/intervenant` et `utils/nature_affaire` ; ces
tests passent par les vraies routes de création et de correction.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session

from app.database import engine
from app.models.core import RoleUtilisateur, StatutUtilisateur, Ticket, Utilisateur
from app.models.prestataires import Prestataire
from app.models.tickets import StatutTicket
from app.routers.tickets import crud, mise_a_jour
from app.schemas import TicketCreate, TicketUpdate
from app.utils.kanban_tickets import colonne_du_ticket
from app.utils.perimetres import arbre


@pytest.fixture()
def session(monkeypatch, batiments):
    monkeypatch.setattr(crud, "_notifier_cs_creation", lambda *a, **k: None, raising=False)
    arbre()
    with Session(engine) as s:
        yield s


def _compte(session, *, role=None):
    u = Utilisateur(
        email=f"int-{uuid.uuid4().hex[:8]}@exemple.test", mot_de_passe_hash="x",
        prenom="P", nom="N", actif=True, statut=StatutUtilisateur.copropriétaire_résident,
        roles_json=role.value if role else "résident",
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _prestataire(session) -> Prestataire:
    p = Prestataire(nom=f"Ascenseurs {uuid.uuid4().hex[:4]}", specialite="ascenseur")
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _creer(session, user, **champs):
    corps = TicketCreate(titre="Visite ascenseur", description="Visite trimestrielle.", **champs)
    return crud.create_ticket(corps, BackgroundTasks(), session=session, user=user)


def _corriger(session, user, ticket_id, **champs):
    return mise_a_jour.update_ticket(
        ticket_id, TicketUpdate(**champs), BackgroundTasks(), session=session, user=user,
    )


# ── L'intervenant et la récurrence ──────────────────────────────────────────

def test_le_conseil_designe_l_intervenant_et_la_recurrence(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    p = _prestataire(session)
    lu = _creer(session, cs, categorie="entretien", prestataire_id=p.id,
                frequence_type="mois", frequence_valeur=3)
    assert (lu.prestataire_id, lu.prestataire_nom) == (p.id, p.nom)
    assert (lu.frequence_type, lu.frequence_valeur) == ("mois", 3)


def test_l_intervenant_ne_vaut_que_pour_le_bati(session):
    """Une question n'a pas d'intervenant ; recatégorisée, l'affaire perd le sien."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    p = _prestataire(session)
    assert _creer(session, cs, categorie="question", prestataire_id=p.id).prestataire_id is None
    t = _creer(session, cs, categorie="panne", prestataire_id=p.id)
    assert _corriger(session, cs, t.id, categorie="question").prestataire_id is None


def test_mensuelle_n_attend_pas_de_nombre(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    lu = _creer(session, cs, categorie="entretien", frequence_type="mois")
    assert (lu.frequence_type, lu.frequence_valeur) == ("mois", 1)


def test_un_resident_ne_designe_pas_l_intervenant(session):
    """Ignoré, pas refusé : sa correction de texte doit passer."""
    resident = _compte(session)
    p = _prestataire(session)
    lu = _creer(session, resident, categorie="panne", prestataire_id=p.id)
    assert lu.prestataire_id is None


def test_un_prestataire_inconnu_est_refuse(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    with pytest.raises(HTTPException) as refus:
        _creer(session, cs, categorie="panne", prestataire_id=987654)
    assert refus.value.status_code == 404


def test_la_recurrence_ne_vaut_que_pour_un_entretien(session):
    """Hors Entretien elle est effacée — même à la recatégorisation."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    lu = _creer(session, cs, categorie="panne", frequence_type="mois", frequence_valeur=3)
    assert (lu.frequence_type, lu.frequence_valeur) == (None, None)

    entretien = _creer(session, cs, categorie="entretien", frequence_type="mois", frequence_valeur=6)
    lu = _corriger(session, cs, entretien.id, categorie="panne")
    assert (lu.frequence_type, lu.frequence_valeur) == (None, None)


def test_une_recurrence_inventee_est_refusee(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    with pytest.raises(HTTPException) as refus:
        _creer(session, cs, categorie="entretien", frequence_type="lunes", frequence_valeur=2)
    assert refus.value.status_code == 422


def test_le_conseil_change_et_efface_l_intervenant(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    p1, p2 = _prestataire(session), _prestataire(session)
    t = _creer(session, cs, categorie="entretien", prestataire_id=p1.id)
    assert _corriger(session, cs, t.id, prestataire_id=p2.id).prestataire_id == p2.id
    assert _corriger(session, cs, t.id, prestataire_id=None).prestataire_id is None


# ── Les catégories du conseil ───────────────────────────────────────────────

@pytest.mark.parametrize("categorie", ["etude_travaux", "entretien", "actualite"])
def test_un_resident_ne_cree_pas_une_categorie_du_conseil(session, categorie):
    resident = _compte(session)
    with pytest.raises(HTTPException) as refus:
        _creer(session, resident, categorie=categorie)
    assert refus.value.status_code == 403


def test_un_resident_ne_passe_pas_vers_une_categorie_du_conseil(session):
    resident = _compte(session)
    t = _creer(session, resident, categorie="panne")
    with pytest.raises(HTTPException) as refus:
        _corriger(session, resident, t.id, categorie="etude_travaux")
    assert refus.value.status_code == 403


def test_l_auteur_d_une_etude_corrige_son_texte_sans_rien_demander(session):
    """GARDER sa catégorie n'est pas y passer : une ancienne étude reste corrigeable."""
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    resident = _compte(session)
    t = _creer(session, cs, categorie="etude_travaux")
    session.get(Ticket, t.id).auteur_id = resident.id
    session.commit()
    lu = _corriger(session, resident, t.id, categorie="etude_travaux", titre="Étude — corrigée")
    assert lu.titre == "Étude — corrigée"


def test_une_categorie_du_conseil_ne_fait_pas_une_actualite(session):
    """🔴 La nature se lit sur « Actualité », pas sur « réservée au conseil ».

    Le test de changement de nature était écrit sur `categorie_reservee` :
    Étude & travaux, réservée depuis ce lot, aurait fait passer une panne à
    l'état `publie` d'une actualité.
    """
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, cs, categorie="panne")
    lu = _corriger(session, cs, t.id, categorie="etude_travaux")
    assert lu.statut == StatutTicket.ouvert.value


# ── Les deux états nés des colonnes du kanban ───────────────────────────────

@pytest.mark.parametrize("statut, colonne", [("en_ag", "ag"), ("chez_prestataire", "fournisseur")])
def test_les_deux_nouveaux_etats_ont_leur_colonne(session, statut, colonne):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, cs, categorie="entretien", statut=statut)
    assert t.statut == statut
    assert colonne_du_ticket(t.statut) == colonne
