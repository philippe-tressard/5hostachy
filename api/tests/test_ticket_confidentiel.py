"""Le drapeau `confidentiel` d'un ticket — qui peut le poser, et où il arrive.

## 🔴 Pourquoi (#710, étape 1)

L'ouverture des tickets aux résidents de leur périmètre est décidée. Elle rendrait
lisibles de tout un bâtiment des affaires qui parlent de personnes.

> **Ouvrir la lecture sans pouvoir refermer un cas particulier est un choix
> irréversible sur des données qui parlent de personnes.**

D'où l'ordre retenu : le drapeau d'abord, l'ouverture ensuite.

⚠️ **À ce stade il ne referme RIEN.** `ticket_visible()` est encore binaire —
auteur, personne pour qui le ticket a été saisi, CS, admin — et personne de neuf
ne voit rien de plus. La règle qui LIT le drapeau viendra avec l'ouverture, dans
le même lot qu'elle : une règle posée d'avance serait inerte, et une règle inerte
est indistinguable d'une règle absente.

Ce qui est vérifiable dès maintenant, et que ce fichier éprouve : **qui a le droit
de poser le drapeau**, et **qu'il arrive bien jusqu'à l'API**.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import RoleUtilisateur, StatutTicket, Ticket, Utilisateur
from app.routers.tickets.commun import ticket_read
from app.routers.tickets.crud import update_ticket
from app.schemas import TicketUpdate
from tests.purge_test import purger_ligne


def _utilisateur(session, roles: str) -> Utilisateur:
    u = Utilisateur(
        email=f"{roles}-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x", prenom="Camille", nom="Sorel",
        roles_json=roles, actif=True,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture()
def contexte():
    """Un ticket, son auteur (résident) et un membre du conseil syndical."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        auteur = _utilisateur(session, "résident")
        cs = _utilisateur(session, "conseil_syndical")
        ticket = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}", titre="Fuite au 3e",
            description="…", categorie="panne", auteur_id=auteur.id,
            statut=StatutTicket.ouvert,
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)
        yield session, ticket, auteur, cs
        purger_ligne(session, Ticket, ticket.id)
        purger_ligne(session, Utilisateur, auteur.id)
        purger_ligne(session, Utilisateur, cs.id)
        session.commit()


def test_un_ticket_nest_pas_confidentiel_par_defaut(contexte):
    """Même choix que `Publication.confidentiel` (#347) — une seule réponse."""
    _session, ticket, _auteur, _cs = contexte
    assert ticket.confidentiel is False


def test_le_conseil_syndical_peut_refermer_un_ticket(contexte):
    session, ticket, _auteur, cs = contexte
    update_ticket(
        ticket.id, TicketUpdate(confidentiel=True), BackgroundTasks(), session=session, user=cs
    )
    session.refresh(ticket)
    assert ticket.confidentiel is True


def test_lauteur_ne_peut_PAS_refermer_son_propre_ticket(contexte):
    """🔴 Le cœur du contrôle.

    Un auteur corrige son texte ; il ne décide pas qui a le droit de le lire. Si
    le drapeau était passé par `_appliquer_contenu`, il serait ouvert à quiconque
    peut éditer le ticket — et « confidentiel » deviendrait une préférence
    personnelle au lieu d'une décision du conseil.
    """
    session, ticket, auteur, _cs = contexte
    with pytest.raises(HTTPException) as e:
        update_ticket(
            ticket.id, TicketUpdate(confidentiel=True), BackgroundTasks(),
            session=session, user=auteur,
        )
    assert e.value.status_code == 403
    session.refresh(ticket)
    assert ticket.confidentiel is False, "un refus n'écrit rien"


def test_le_drapeau_arrive_jusqua_lapi(contexte):
    """⚠️ Le défaut SYMÉTRIQUE de celui du 02/09/2026.

    Un champ passé à un schéma qui ne le déclare pas est ignoré par Pydantic —
    `test_schemas_champs.py` l'attrape. Un champ DÉCLARÉ et jamais rempli, lui,
    prend sa valeur par défaut : ici `False`, c'est-à-dire « aucun ticket n'est
    confidentiel », sur une API qui a l'air de répondre.

    Ce test-ci est le seul qui puisse le voir.
    """
    session, ticket, _auteur, cs = contexte
    assert ticket_read(ticket, session).confidentiel is False
    update_ticket(
        ticket.id, TicketUpdate(confidentiel=True), BackgroundTasks(), session=session, user=cs
    )
    session.refresh(ticket)
    assert ticket_read(ticket, session).confidentiel is True, (
        "le drapeau ne sort pas de `ticket_read` — il est déclaré au schéma mais "
        "jamais rempli, donc figé à False pour tout le monde"
    )
