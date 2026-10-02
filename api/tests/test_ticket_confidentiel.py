"""Le drapeau `confidentiel` d'un ticket — qui peut le poser, et où il arrive.

## 🔴 Pourquoi (#710)

L'ouverture des tickets aux résidents de leur périmètre rendait lisibles de tout
un bâtiment des affaires qui parlent de personnes.

> **Ouvrir la lecture sans pouvoir refermer un cas particulier est un choix
> irréversible sur des données qui parlent de personnes.**

D'où l'ordre retenu : le drapeau d'abord, l'ouverture ensuite. Il est désormais
LU par `ticket_visible()` : un ticket confidentiel se referme pour le voisin, pas
pour son auteur ni pour le conseil (`test_tickets_visibilite_perimetre.py`).

Ce que ce fichier éprouve : **le défaut** (ouvert) et **qui a le droit de poser
le drapeau** — le conseil, jamais l'auteur. Qu'il arrive jusqu'à l'API est tenu,
pour toutes les colonnes à la fois, par
`test_ticket_read_rend_le_modele.py::test_chaque_colonne_partagee_revient_telle_quelle`.

⚠️ `Publication.confidentiel` (#347) a disparu avec l'objet le 30/09/2026 (#1177) :
une actualité est un ticket, et porte donc ce drapeau-ci.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import StatutTicket, Ticket, Utilisateur
from app.routers.tickets.mise_a_jour import update_ticket
from app.schemas import TicketUpdate
from tests.aides_base import compte
from tests.aides_purge import purger_ligne


@pytest.fixture()
def contexte():
    """Un ticket, son auteur (résident) et un membre du conseil syndical."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        auteur = compte(session, prefixe="résident", roles_json="résident")
        cs = compte(session, prefixe="conseil_syndical", roles_json="conseil_syndical")
        ticket = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Fuite au 3e",
            description="…",
            categorie="panne",
            auteur_id=auteur.id,
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
    """Ouvert par défaut : refermer est une décision du conseil, pas un état initial."""
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
            ticket.id,
            TicketUpdate(confidentiel=True),
            BackgroundTasks(),
            session=session,
            user=auteur,
        )
    assert e.value.status_code == 403
    session.refresh(ticket)
    assert ticket.confidentiel is False, "un refus n'écrit rien"
