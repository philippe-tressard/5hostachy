"""Une ÉDITION écrit une correction, jamais une étape de workflow.

## Pourquoi ce garde-fou (#433, 18/08/2026)

Le cadre #430 rouvre le workflow à l'édition : *l'édition corrige — une erreur,
un oubli, un complément — et l'état s'y corrige comme les autres champs*. Cela
n'est tenable qu'à une condition : que le `PATCH` n'écrive pas la même ligne
qu'une vraie transition. Sinon corriger un état mal saisi ferait apparaître dans
l'Historique une étape que l'objet n'a jamais franchie — le ticket aurait « été »
en cours alors qu'il n'y est jamais passé.

Le remède a été posé sur les **tickets** par #431 et **n'était couvert par aucun
test**. Il l'est ici, en même temps que son jumeau côté **publications** (#433) :
même défaut, même remède, et donc un seul fichier — deux entités qui divergent
sur ce point sont exactement ce que le cadre supprime.

⚠️ Ce test vérifie **le fait** (ce qui est écrit dans le fil), pas le symptôme
attendu : il relit les évolutions en base après l'appel, au lieu de se fier au
code de retour de l'endpoint (`standards/04` §14 — observer la chose, pas son
enregistrement).
"""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Publication, PublicationEvolution, RoleUtilisateur, Ticket, TicketEvolution,
    Utilisateur,
)
from app.routers.publications.crud import update_publication
from app.routers.tickets.crud import update_ticket
from app.schemas import PublicationUpdate, TicketUpdate

PREFIXE_CORRECTION = "Correction"


@pytest.fixture()
def cs() -> Utilisateur:
    """Un membre du conseil syndical, seul habilité à corriger l'état."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        membre = Utilisateur(
            email=f"cs-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x",
            prenom="Camille",
            nom="Sorel",
            role=RoleUtilisateur.conseil_syndical,
        )
        session.add(membre)
        session.commit()
        session.refresh(membre)
        yield membre
        session.delete(session.get(Utilisateur, membre.id))
        session.commit()


# ── Publications ──────────────────────────────────────────────────────────────

def test_patch_publication_ecrit_une_correction_et_pas_une_transition(cs):
    with Session(engine) as session:
        pub = Publication(
            titre="Ravalement",
            contenu="<p>Début des travaux.</p>",
            auteur_id=cs.id,
            statut="publie",
            perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
            public_cible='["résidents"]',
        )
        session.add(pub)
        session.commit()
        session.refresh(pub)

        update_publication(
            pub.id, PublicationUpdate(statut="resolu", titre="Ravalement du bâtiment 2"),
            BackgroundTasks(), session, cs,
        )

        evols = session.exec(
            select(PublicationEvolution)
            .where(PublicationEvolution.publication_id == pub.id)
        ).all()

        assert [e.type for e in evols] == ["commentaire"], (
            "Une édition ne doit écrire AUCUNE évolution de type « etat » : "
            f"trouvé {[e.type for e in evols]}."
        )
        ligne = evols[0].contenu or ""
        assert ligne.startswith(PREFIXE_CORRECTION), ligne
        assert "État : Publié → Résolu" in ligne, ligne
        assert "Titre" in ligne, "La correction doit dire TOUT ce qui a changé : " + ligne
        #  La ligne ne porte ni `ancien_statut` ni `nouveau_statut` : sans eux,
        #  aucun jalon de suivi ne se dessine dans le fil.
        assert evols[0].ancien_statut is None and evols[0].nouveau_statut is None
        #  Le fait, lui, est enregistré : l'état a bien changé.
        assert session.get(Publication, pub.id).statut == "resolu"

        for e in evols:
            session.delete(e)
        session.delete(session.get(Publication, pub.id))
        session.commit()


def test_patch_publication_sans_changement_n_ecrit_rien(cs):
    """Réenregistrer les mêmes valeurs n'est pas une correction.

    Le cas zéro de ce mécanisme : un `PATCH` qui renvoie ce qui était déjà là ne
    doit pas remplir l'Historique de lignes vides. C'est ce que garantit le relevé
    de l'état d'AVANT, et rien d'autre.
    """
    with Session(engine) as session:
        pub = Publication(
            titre="Ravalement",
            contenu="<p>Début des travaux.</p>",
            auteur_id=cs.id,
            statut="publie",
            perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
            public_cible='["résidents"]',
        )
        session.add(pub)
        session.commit()
        session.refresh(pub)

        update_publication(
            pub.id, PublicationUpdate(titre="Ravalement", statut="publie"),
            BackgroundTasks(), session, cs,
        )

        evols = session.exec(
            select(PublicationEvolution)
            .where(PublicationEvolution.publication_id == pub.id)
        ).all()
        assert evols == [], f"Aucune ligne attendue, trouvé : {[e.contenu for e in evols]}"

        session.delete(session.get(Publication, pub.id))
        session.commit()


# ── Tickets — le même remède, posé par #431 et jamais gardé ───────────────────

def test_patch_ticket_ecrit_une_correction_et_pas_une_transition(cs):
    with Session(engine) as session:
        ticket = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Ascenseur en panne",
            description="<p>Bloqué au 3ᵉ.</p>",
            categorie="panne",
            statut="ouvert",
            auteur_id=cs.id,
            perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)

        update_ticket(
            ticket.id, TicketUpdate(statut="en_cours"), BackgroundTasks(), session, cs,
        )

        evols = session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).all()

        assert [e.type for e in evols] == ["commentaire"], (
            f"Une édition ne doit écrire aucune transition : {[e.type for e in evols]}."
        )
        assert (evols[0].contenu or "").startswith(PREFIXE_CORRECTION), evols[0].contenu
        assert "État :" in (evols[0].contenu or ""), evols[0].contenu
        assert session.get(Ticket, ticket.id).statut == "en_cours"

        for e in evols:
            session.delete(e)
        session.delete(session.get(Ticket, ticket.id))
        session.commit()
