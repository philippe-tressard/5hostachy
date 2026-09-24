"""Un BOGUE (#1191, 24/09/2026) — arbitré par l'utilisateur :

« tout le monde peut en détecter un et donc en ouvrir un, mais seul le
gestionnaire est notifié, et la rubrique Périmètre n'a pas de sens et doit être
verrouillée ».
"""

from __future__ import annotations

from fastapi import BackgroundTasks
from sqlmodel import select

from app.models.core import ConfigSite, Notification, RoleUtilisateur
from app.routers.tickets import crud
from app.schemas import TicketCreate
from tests.aides_badges import _compte, session  # noqa: F401 — `session` est une fixture


def _creer(session, auteur, **champs):
    corps = TicketCreate(titre="Le bouton ne répond pas", description="Rien ne se passe.", **champs)
    return crud.create_ticket(corps, BackgroundTasks(), session=session, user=auteur)


def _avec_gestionnaire(session):
    gestionnaire = _compte(session, "Gestionnaire")
    session.add(ConfigSite(cle="site_manager_user_id", valeur=str(gestionnaire.id)))
    session.commit()
    return gestionnaire


def test_seul_le_gestionnaire_est_prevenu(session):
    gestionnaire = _avec_gestionnaire(session)
    conseiller = _compte(session, "Conseil")
    conseiller.roles_json = RoleUtilisateur.conseil_syndical.value
    conseiller.actif = (
        True  # sans lui, le conseil ne serait prévenu de rien : le test ne prouverait rien
    )
    session.add(conseiller)
    session.commit()
    resident = _compte(session, "Resident")

    _creer(session, resident, categorie="bug")

    destinataires = {n.destinataire_id for n in session.exec(select(Notification)).all()}
    assert destinataires == {gestionnaire.id}, "le conseil syndical a été prévenu d'un bogue"


def test_le_perimetre_d_un_bogue_est_verrouille(session):
    _avec_gestionnaire(session)
    lu = _creer(session, _compte(session, "Resident"), categorie="bug", perimetre_cible=["bat:1"])
    assert lu.perimetre_cible == ["résidence"]


def test_cas_zero_une_panne_previent_toujours_le_conseil(session):
    """Sans lui, une règle qui couperait toutes les notifications passerait."""
    _avec_gestionnaire(session)
    conseiller = _compte(session, "Conseil")
    conseiller.roles_json = RoleUtilisateur.conseil_syndical.value
    conseiller.actif = (
        True  # sans lui, le conseil ne serait prévenu de rien : le test ne prouverait rien
    )
    session.add(conseiller)
    session.commit()
    _creer(session, _compte(session, "Resident"), categorie="panne")
    assert conseiller.id in {n.destinataire_id for n in session.exec(select(Notification)).all()}
