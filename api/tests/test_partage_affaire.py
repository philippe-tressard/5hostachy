"""Transmettre une affaire par courriel (#1357) — qui le peut, et ce qui part.

Option E : le 🔗 copie le lien, puis propose « L'envoyer par courriel ».
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import StatutTicket, StatutUtilisateur, Ticket, Utilisateur
from app.routers.tickets.partage import PartageCourriel, partager_par_courriel
from app.utils.limiter import LIMITE_PARTAGE_COURRIEL
from tests.conftest import requete_de_test
from tests.purge_test import purger_ligne


def _compte(session, statut, roles="résident") -> Utilisateur:
    u = Utilisateur(
        email=f"partage-{uuid.uuid4().hex[:8]}@exemple.test",
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
def monde(batiments):
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        auteur = _compte(session, StatutUtilisateur.copropriétaire_résident)
        locataire = _compte(session, StatutUtilisateur.locataire)
        t = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Fuite au 3e",
            description="Le détail qui ne doit pas partir.",
            categorie="nuisance",
            auteur_id=auteur.id,
            statut=StatutTicket.ouvert,
            perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
        )
        session.add(t)
        session.commit()
        session.refresh(t)
        yield session, t, auteur, locataire
        purger_ligne(session, Ticket, t.id)
        for u in (auteur, locataire):
            purger_ligne(session, Utilisateur, u.id)
        session.commit()


def _partager(session, t, user):
    taches = BackgroundTasks()
    partager_par_courriel(
        requete_de_test(f"/tickets/{t.id}/partager"),
        t.id,
        PartageCourriel(email="voisin@exemple.fr"),
        taches,
        session=session,
        user=user,
    )
    return taches


def test_qui_lit_l_affaire_peut_la_transmettre(monde):
    session, t, auteur, _locataire = monde
    taches = _partager(session, t, auteur)
    assert len(taches.tasks) == 1
    envoi = taches.tasks[0]
    assert envoi.kwargs["code"] == "ticket_partage"
    assert envoi.kwargs["to"] == "voisin@exemple.fr"
    #  Titre, numéro, lien — jamais la description.
    assert set(envoi.kwargs["context"]["ticket"]) == {"id", "numero", "titre"}


def test_qui_ne_lit_pas_l_affaire_recoit_le_refus_de_sa_fiche(monde):
    """Une affaire suivie n'est pas lue d'un locataire : il ne la transmet pas —
    même réponse que sa fiche (`get_ticket`)."""
    session, t, _auteur, locataire = monde
    with pytest.raises(HTTPException) as refus:
        _partager(session, t, locataire)
    assert refus.value.status_code == 403


def test_l_envoi_est_plafonne_a_l_heure():
    """3 par minute ne suffit pas : tenus une heure, ce serait 180 envois."""
    assert "/hour" in LIMITE_PARTAGE_COURRIEL
