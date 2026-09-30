"""Les aides des tests d'affaire — créer, corriger, un compte, une session.

Elles vivaient dans `test_intervenant_affaire.py`, et trois autres fichiers les
importaient DEPUIS un fichier de tests (`test_equipement_affaire`,
`test_suite_conseil`, `test_trace_droits`) : fusionner ou découper ce fichier-là
aurait cassé les trois. Elles vivent ici, comme `aides_badges.py`, plutôt que
d'être recopiées. `session` est une fixture : un fichier de tests l'IMPORTE
pour que pytest la trouve.

Elles passent par les VRAIES routes de création et de correction.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, select

from app.database import engine
from app.models.core import StatutUtilisateur, Utilisateur
from app.models.prestataires import ContratEntretien
from app.routers.tickets import crud, mise_a_jour
from app.schemas import TicketCreate, TicketUpdate
from app.utils.perimetres import arbre


@pytest.fixture()
def session(monkeypatch, batiments):
    monkeypatch.setattr(crud, "_notifier_cs_creation", lambda *a, **k: None, raising=False)
    arbre()
    with Session(engine) as s:
        yield s
        #  Les contrats partent AVANT le patrimoine : la fixture `batiments`
        #  supprime la copropriété, et SQLAlchemy dénouerait alors leur
        #  `copropriete_id` (NOT NULL) — le test suivant tombait au montage.
        for c in s.exec(select(ContratEntretien)).all():
            s.delete(c)
        s.commit()


def _compte(session, *, role=None):
    u = Utilisateur(
        email=f"int-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x",
        prenom="P",
        nom="N",
        actif=True,
        statut=StatutUtilisateur.copropriétaire_résident,
        roles_json=role.value if role else "résident",
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _creer(session, user, **champs):
    corps = TicketCreate(titre="Visite ascenseur", description="Visite trimestrielle.", **champs)
    return crud.create_ticket(corps, BackgroundTasks(), session=session, user=user)


def _corriger(session, user, ticket_id, **champs):
    return mise_a_jour.update_ticket(
        ticket_id,
        TicketUpdate(**champs),
        BackgroundTasks(),
        session=session,
        user=user,
    )
