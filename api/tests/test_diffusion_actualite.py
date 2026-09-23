"""Ce qu'une affaire « Actualité » fait partir (#1091, lot 4 ; #1096).

On crée et on corrige par les VRAIES routes, et l'on regarde les tâches mises en
file : message sur le groupe, courriel au syndic / au CS, affiche.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session

import app.routers.annonces_hall as annonces_hall
import app.routers.tickets.crud as crud
import app.routers.tickets.mise_a_jour as mise_a_jour
import app.utils.whatsapp as whatsapp
from app.database import engine
from app.models.core import RoleUtilisateur, Utilisateur
from app.schemas import TicketCreate, TicketUpdate
from app.utils.perimetres import arbre


@pytest.fixture()
def contexte(monkeypatch, batiments):
    affiches: list[int] = []
    monkeypatch.setattr(whatsapp, "config_whatsapp", lambda s, *a: {"site_url": "https://5hostachy.fr"})
    monkeypatch.setattr(whatsapp, "whatsapp_actif", lambda c: True)
    monkeypatch.setattr(
        "app.utils.destinataires.destinataires_syndic_cs",
        lambda session, syndic, cs: [("Syndic", "syndic@exemple.fr")] if (syndic or cs) else [],
    )
    monkeypatch.setattr(annonces_hall, "creer_annonce_hall", lambda **k: affiches.append(k["ticket_id"]))
    arbre()
    with Session(engine) as s:
        cs = Utilisateur(
            email=f"cs-{uuid.uuid4().hex[:8]}@exemple.test", mot_de_passe_hash="x",
            prenom="C", nom="S", actif=True, roles_json=RoleUtilisateur.conseil_syndical.value,
        )
        s.add(cs)
        s.commit()
        s.refresh(cs)
        yield s, cs, affiches, batiments


def _noms(taches: BackgroundTasks) -> list[str]:
    return [t.func.__name__ for t in taches.tasks]


def _creer(s, cs, **champs):
    taches = BackgroundTasks()
    corps = TicketCreate(
        titre="Coupure d'eau", description="Jeudi 9h-12h.", categorie="actualite",
        partager_whatsapp=True, destinataire_syndic=True, annonce_hall=True, **champs,
    )
    lu = crud.create_ticket(corps, taches, session=s, user=cs)
    return lu, taches


def test_une_actualite_ouverte_part_partout_avec_le_lien_de_l_affaire(contexte):
    s, cs, affiches, _ = contexte
    lu, taches = _creer(s, cs)
    assert "envoyer_whatsapp_avec_log" in _noms(taches)
    wa = next(t for t in taches.tasks if t.func.__name__ == "envoyer_whatsapp_avec_log")
    assert wa.kwargs["lien"] == f"https://5hostachy.fr/tickets/{lu.id}"
    courriel = next(t for t in taches.tasks if t.func.__name__ == "send_email_group")
    assert courriel.kwargs["code"] == "publication_syndic"
    assert courriel.kwargs["context"]["publication"]["lien"] == f"/tickets/{lu.id}"
    assert affiches == [lu.id]


def test_reservee_au_conseil_rien_ne_part(contexte):
    """#1096 : Destinataires = « Conseil syndical » SEUL vaut l'ancienne 🛡️."""
    s, cs, affiches, _ = contexte
    _lu, taches = _creer(s, cs, public_cible=["conseil_syndical"])
    assert _noms(taches) == []
    assert affiches == []


def test_reservee_au_perimetre_pas_d_affiche(contexte):
    """Un hall n'a aucun contrôle d'accès : 🔒 exclut l'affiche."""
    s, cs, affiches, batiments = contexte
    _lu, taches = _creer(s, cs, reserve_perimetre=True, perimetre_cible=[f"bat:{batiments[0]}"])
    assert affiches == []
    assert "envoyer_whatsapp_avec_log" in _noms(taches), "le groupe reçoit le message restreint"


def test_lever_la_reserve_fait_partir_ce_qui_etait_retenu(contexte):
    s, cs, _affiches, _ = contexte
    lu, taches = _creer(s, cs, public_cible=["conseil_syndical"])
    assert _noms(taches) == []
    taches = BackgroundTasks()
    mise_a_jour.update_ticket(lu.id, TicketUpdate(public_cible=["copropriétaires"]), taches, session=s, user=cs)
    assert "send_email_group" in _noms(taches), "le courriel au syndic retenu doit partir"
