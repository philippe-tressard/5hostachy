"""Le conseil pose Quand, Intervenant et Équipement dans une SUITE (#1207, 24/09/2026).

Arbitré par l'utilisateur : « via la Suite 🔄 ». Un membre du conseil qui n'est pas
administrateur n'avait aucun chemin d'écran pour le faire sur l'affaire d'un
résident : le crayon ne lui est pas montré, et le serveur refuse qu'il en
réécrive le texte. Mêmes règles que la correction ; la trace est au fil.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import BackgroundTasks

from app.models.core import RoleUtilisateur, Ticket, TicketEvolution
from app.routers.tickets import evolutions
from app.schemas_tickets import TicketEvolutionCreate
from tests.test_intervenant_affaire import _compte, _creer, session  # noqa: F401


def _suite(session, user, ticket_id, **champs):
    corps = TicketEvolutionCreate(
        type="commentaire", contenu="<p>Pris en charge.</p>", notifier=False, **champs
    )
    return evolutions.add_evolution(ticket_id, corps, BackgroundTasks(), session=session, user=user)


def test_le_conseil_planifie_l_affaire_d_un_resident_par_une_suite(session):
    resident = _compte(session)
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, resident, categorie="panne")
    _suite(session, cs, t.id, equipement="toiture", debut=datetime(2026, 10, 2, 9, 0))
    lu = session.get(Ticket, t.id)
    assert (lu.equipement, lu.debut) == ("toiture", datetime(2026, 10, 2, 9, 0))
    #  La trace est AU FIL : la Suite dit ce qu'elle a posé.
    derniere = max(
        session.exec(
            evolutions.select(TicketEvolution).where(TicketEvolution.ticket_id == t.id)
        ).all(),
        key=lambda e: e.id,
    )
    assert "Équipement" in derniere.contenu and "Quand" in derniere.contenu


def test_un_resident_ne_planifie_pas_par_une_suite(session):
    """Ignoré, pas refusé : sa suite passe, sans rien poser."""
    resident = _compte(session)
    t = _creer(session, resident, categorie="panne")
    _suite(session, resident, t.id, equipement="toiture", debut=datetime(2026, 10, 2, 9, 0))
    lu = session.get(Ticket, t.id)
    assert (lu.equipement, lu.debut) == (None, None)


def test_cas_zero_une_suite_muette_ne_touche_a_rien(session):
    cs = _compte(session, role=RoleUtilisateur.conseil_syndical)
    t = _creer(session, cs, categorie="panne", equipement="vmc")
    _suite(session, cs, t.id)
    assert session.get(Ticket, t.id).equipement == "vmc"
