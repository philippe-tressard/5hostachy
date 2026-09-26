"""Les DESTINATAIRES d'une affaire suivie (#1343) — qui les écrit, et quand.

Qui les LIT est éprouvé ailleurs, contre la pastille de lecture
(`test_lecture_pastille.py`, `donnees/lecture_pastille.json`). Ce fichier tient
ce qui l'y amène :

1. le conseil les pose depuis une Suite, sur une affaire comme sur une actualité ;
2. une actualité promue en affaire PERD son public visé — il déciderait qui la
   lit sans que personne l'ait choisi pour elle —, sauf s'il est renvoyé dans
   la même correction (l'écran montre les Destinataires, ce qu'il montre part) ;
3. vides, rien ne change : la règle par défaut décide.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import StatutTicket, StatutUtilisateur, Ticket, Utilisateur
from app.routers.tickets.evolutions import add_evolution
from app.routers.tickets.mise_a_jour import update_ticket
from app.schemas import TicketEvolutionCreate, TicketUpdate
from app.utils.visibility import ticket_visible
from tests.purge_test import purger_ligne


def _compte(session, roles: str, statut=None) -> Utilisateur:
    u = Utilisateur(
        email=f"dest-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x",
        prenom="Camille",
        nom="Sorel",
        roles_json=roles,
        statut=statut,
        actif=True,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture()
def contexte(batiments):
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        cs = _compte(session, "conseil_syndical")
        locataire = _compte(session, "résident", StatutUtilisateur.locataire)
        locataire.batiment_id = batiments[0]
        session.add(locataire)
        session.commit()
        crees: list[Ticket] = []

        def affaire(
            categorie="nuisance", public=None
        ) -> Ticket:  # pas « panne » : sa lecture par défaut lui est propre (#1343)
            t = Ticket(
                numero=f"T-{uuid.uuid4().hex[:6]}",
                titre="Fuite au 3e",
                description="…",
                categorie=categorie,
                auteur_id=cs.id,
                statut=StatutTicket.publie if categorie == "actualite" else StatutTicket.ouvert,
                perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
                public_cible=json.dumps(public) if public else None,
            )
            session.add(t)
            session.commit()
            session.refresh(t)
            crees.append(t)
            return t

        yield session, cs, locataire, affaire
        for t in crees:
            purger_ligne(session, Ticket, t.id)
        for u in (cs, locataire):
            purger_ligne(session, Utilisateur, u.id)
        session.commit()


def test_sans_choix_une_affaire_suivie_reste_fermee_aux_locataires(contexte):
    session, _cs, locataire, affaire = contexte
    assert not ticket_visible(affaire(), locataire)


def test_le_conseil_pose_les_destinataires_d_une_affaire_depuis_une_suite(contexte):
    session, cs, locataire, affaire = contexte
    t = affaire()
    add_evolution(
        t.id,
        TicketEvolutionCreate(
            type="commentaire", contenu="Ouverte aux locataires.", public_cible=["locataires"]
        ),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    session.refresh(t)
    assert json.loads(t.public_cible) == ["locataires"]
    assert ticket_visible(t, locataire)


def test_revenir_au_defaut_depuis_une_suite_efface_le_choix(contexte):
    session, cs, locataire, affaire = contexte
    t = affaire(public=["locataires"])
    add_evolution(
        t.id,
        TicketEvolutionCreate(type="commentaire", contenu="Retour à la règle.", public_cible=[]),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    session.refresh(t)
    assert t.public_cible is None
    assert not ticket_visible(t, locataire)


def test_une_actualite_promue_perd_son_public_vise(contexte):
    """Le résidu que la migration 0228 efface en base, effacé aussi au geste."""
    session, cs, locataire, affaire = contexte
    t = affaire(categorie="actualite", public=["locataires"])
    update_ticket(
        t.id, TicketUpdate(categorie="nuisance"), BackgroundTasks(), session=session, user=cs
    )
    session.refresh(t)
    assert t.public_cible is None
    assert not ticket_visible(t, locataire)


def test_promue_avec_ses_destinataires_renvoyes_elle_les_garde(contexte):
    session, cs, locataire, affaire = contexte
    t = affaire(categorie="actualite", public=["locataires"])
    update_ticket(
        t.id,
        TicketUpdate(categorie="nuisance", public_cible=["locataires"]),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    session.refresh(t)
    assert json.loads(t.public_cible) == ["locataires"]
    assert ticket_visible(t, locataire)
