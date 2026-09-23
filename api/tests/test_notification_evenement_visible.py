"""Une notification d'événement ne va qu'à qui peut le VOIR (#1166).

## Le défaut du 23/09/2026

À la création d'une « coupure » ou de « travaux », `routers/calendrier.py`
posait une notification — titre ET description — pour **tous** les comptes
actifs. Un événement réservé au conseil syndical, ou limité à un bâtiment, était
donc annoncé à toute la copropriété : la réserve tenait à l'écran du calendrier
et fuyait par la cloche.

La règle de visibilité existe, `evenement_visible` : ce test vérifie que la
notification la suit, sans la réécrire.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, select

import app.routers.calendrier as calendrier
from app.database import engine
from app.models.core import Notification, RoleUtilisateur, Utilisateur
from app.models.evenement import TypeEvenement
from app.schemas_evenement import EvenementCreate
from app.utils.perimetres import arbre


@pytest.fixture()
def session(monkeypatch, batiments):
    """La base partagée des tests : l'arbre des périmètres y est semé par
    `batiments` (conftest) — sans lui, « résidence » ne désigne aucun nœud et
    plus personne ne voit rien, ce qui rendrait ce test vert pour rien."""
    #  Les canaux (WhatsApp, courriels) ont leurs propres tests : ici, seule la
    #  notification dans l'application est en cause.
    monkeypatch.setattr(calendrier, "notifier_canaux", lambda *a, **k: None)
    #  ⚠️ L'arbre se charge AVANT la création : la base de test `:memory:` n'a
    #  qu'UNE connexion, et `arbre()` la referme en se chargeant au milieu de la
    #  transaction de `create_evenement` — qui perd alors son événement. En
    #  production (un fichier, des connexions distinctes), le cas n'existe pas.
    arbre()
    with Session(engine) as s:
        yield s


def _compte(session, email, role=None):
    kw = {"role": role} if role else {}
    email = f"{uuid.uuid4().hex[:8]}-{email}"
    u = Utilisateur(email=email, mot_de_passe_hash="x", prenom="P", nom="N", actif=True, **kw)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _notifies(session, cs, **champs) -> set[int]:
    corps = EvenementCreate(
        titre="Coupure d'eau", description="Jeudi matin.", type=TypeEvenement.coupure,
        debut="2026-10-01T09:00:00", **champs,
    )
    ev = calendrier.create_evenement(corps, BackgroundTasks(), session=session, user=cs)
    return {
        n.destinataire_id for n in session.exec(select(Notification)).all()
        if n.lien and n.lien.endswith(f"-{ev.id}")
    }


def test_un_evenement_reserve_au_conseil_ne_notifie_pas_les_residents(session):
    resident = _compte(session, "r@exemple.fr")
    cs = _compte(session, "cs@exemple.fr", RoleUtilisateur.conseil_syndical)
    notifies = _notifies(session, cs, reserve_cs=True)
    assert resident.id not in notifies, "la réserve fuyait par la notification"
    assert cs.id in notifies


def test_un_evenement_ouvert_notifie_les_residents(session):
    """Témoin : sans lui, le test précédent passerait si plus personne n'était notifié."""
    resident = _compte(session, "r@exemple.fr")
    cs = _compte(session, "cs@exemple.fr", RoleUtilisateur.conseil_syndical)
    assert resident.id in _notifies(session, cs)
