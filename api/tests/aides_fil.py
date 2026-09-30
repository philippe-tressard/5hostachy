"""Un membre du conseil et le nettoyage d'une affaire, pour les tests du fil.

`test_tri_tickets_activite.py` et `test_suite_actualite_ciblage.py` portaient la
même fixture `cs` et le même `_nettoyer`, recopiés à l'identique. Un fichier de
tests ne s'importe pas depuis un autre — `test_aides_de_tests_source_unique.py`
le refuse — : ce qu'ils partagent vit ici (#1495).

`cs` est une fixture : un fichier de tests l'IMPORTE pour que pytest la trouve
(même forme qu'`aides_affaire.session`).
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import RoleUtilisateur, Ticket, TicketEvolution, Utilisateur
from tests.aides_base import compte
from tests.purge_test import purger_ligne


@pytest.fixture()
def cs() -> Utilisateur:
    """Un membre du conseil syndical, dans la base de l'application, purgé à la sortie."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        membre = compte(
            session,
            prefixe="cs",
            prenom="Camille",
            nom="Sorel",
            role=RoleUtilisateur.conseil_syndical,
        )
        yield membre
        purger_ligne(session, Utilisateur, membre.id)
        session.commit()


def nettoyer_affaires(session: Session, *ids: int) -> None:
    """Retire ces affaires, leurs évolutions d'abord : elles les référencent."""
    for tid in ids:
        for e in session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == tid)
        ).all():
            session.delete(e)
        purger_ligne(session, Ticket, tid)
    session.commit()
