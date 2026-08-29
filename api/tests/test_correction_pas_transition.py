"""Une ÉDITION écrit une correction, jamais une étape de workflow.

## Pourquoi ce garde-fou (#433, 18/08/2026)

Le cadre #430 rouvre le workflow à l'édition : *l'édition corrige — une erreur,
un oubli, un complément — et l'état s'y corrige comme les autres champs*. Cela
n'est tenable qu'à une condition : que le `PATCH` n'écrive pas la même ligne
qu'une vraie transition. Sinon corriger un état mal saisi ferait apparaître dans
l'Historique une étape que l'objet n'a jamais franchie — le ticket aurait « été »
en cours alors qu'il n'y est jamais passé.

Le remède a été posé sur les **tickets** par #431 et **n'était couvert par aucun
test**. Il l'est ici, avec ses jumeaux côté **publications** (#433) et
**calendrier** (18/08/2026) : même défaut, même remède, et donc un seul fichier —
trois entités qui divergeraient sur ce point sont exactement ce que le cadre
supprime.

⚠️ Le calendrier a une nuance, et elle est vérifiée : son **Kanban EST son
workflow**, donc un changement de colonne est une **transition tracée** (avec son
avant et son après), pendant que toute autre modification reste une correction.
C'est la même règle vue des deux côtés.

⚠️ Ce test vérifie **le fait** (ce qui est écrit dans le fil), pas le symptôme
attendu : il relit les évolutions en base après l'appel, au lieu de se fier au
code de retour de l'endpoint (`standards/04` §14 — observer la chose, pas son
enregistrement).
"""
from __future__ import annotations


import json
import uuid
from datetime import datetime

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import (
    Evenement, Publication, PublicationEvolution, RoleUtilisateur, Ticket,
    TicketEvolution, TypeEvenement, Utilisateur,
)
from app.models.evenement import EvenementEvolution
from app.routers.calendrier import EvenementUpdate, update_evenement
from app.routers.publications.crud import update_publication
from app.routers.tickets.crud import update_ticket
from app.schemas import PublicationUpdate, TicketUpdate

#  🔴 La purge passe par le code de PRODUCTION : supprimer une ligne sans ce
#  qui la référence est ce que les clés étrangères refusent (#546).
from tests.purge_test import purger_ligne

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
        purger_ligne(session, Utilisateur, membre.id)
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
        purger_ligne(session, Publication, pub.id)
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

        purger_ligne(session, Publication, pub.id)
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
        purger_ligne(session, Ticket, ticket.id)
        session.commit()


def test_patch_ticket_corriger_un_champ_n_ecrit_rien_dans_le_fil(cs):
    """Corriger la CATÉGORIE (ou tout autre champ) ne doit rien inscrire.

    🔴 Signalé à l'écran le 18/08/2026 : *« j'ai fait une édition d'un ticket pour
    corriger sa catégorie et ça m'a créé un historique ! c'est à supprimer »*.

    L'Historique raconte la vie du dossier — ce que le conseil syndical a fait, où
    en est la demande. Une faute de frappe rattrapée n'en fait pas partie : elle
    ajoute une ligne qui n'apprend rien et pousse vers le bas celles qui apprennent
    quelque chose.

    ⚠️ Ce test vérifie AUSSI que la correction a bien été appliquée. Sans cela, il
    passerait au vert sur un endpoint qui n'écrit plus rien du tout — un « rien dans
    le fil » obtenu en ne faisant rien serait le pire des faux verts.
    """
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

        #  Le formulaire d'édition renvoie TOUTES les sections à chaque
        #  enregistrement — c'est ce qui permet d'effacer un champ. On reproduit ce
        #  comportement : seule la catégorie diffère de l'existant.
        update_ticket(
            ticket.id,
            TicketUpdate(
                titre="Ascenseur en panne",
                description="<p>Bloqué au 3ᵉ.</p>",
                categorie="urgence",
                perimetre_cible=["résidence"],
                photos_urls=[],
                fichiers_urls=[],
            ),
            BackgroundTasks(), session, cs,
        )

        evols = session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).all()
        assert evols == [], (
            "Corriger un champ ne doit RIEN écrire dans l'Historique : "
            f"{[(e.type, e.contenu) for e in evols]}"
        )
        #  Le fait, pas le symptôme : la correction a-t-elle été appliquée ?
        assert session.get(Ticket, ticket.id).categorie == "urgence"

        purger_ligne(session, Ticket, ticket.id)
        session.commit()


def test_patch_ticket_sans_rien_changer_n_ecrit_rien(cs):
    """Réenregistrer à l'identique n'écrit rien — même quand l'état est renvoyé.

    C'est l'autre moitié du défaut du 18/08/2026 : quatre champs n'étaient PAS
    comparés à l'existant (description, périmètre, pièces jointes, photos) et un
    cinquième ne l'était pas non plus (« Saisi pour »). Leur seule présence dans le
    `PATCH` suffisait à écrire « modifié ». Corriger le seul périmètre inscrivait
    donc cinq mentions dont une seule était vraie.
    """
    with Session(engine) as session:
        ticket = Ticket(
            numero=f"T-{uuid.uuid4().hex[:6]}",
            titre="Porte du hall",
            description="<p>Grince.</p>",
            categorie="panne",
            #  « ouvert » et non « en_cours » : hors admin, le contenu d'un ticket
            #  ne se corrige que tant qu'il est ouvert — une fois le suivi engagé,
            #  réécrire le texte ferait mentir ce que le CS a lu avant d'agir.
            #  C'est une règle voulue, et mon premier jet du test l'ignorait.
            statut="ouvert",
            auteur_id=cs.id,
            perimetre_cible=json.dumps(["résidence"], ensure_ascii=False),
            photos_urls=json.dumps([], ensure_ascii=False),
            fichiers_urls=json.dumps([], ensure_ascii=False),
        )
        session.add(ticket)
        session.commit()
        session.refresh(ticket)

        update_ticket(
            ticket.id,
            TicketUpdate(
                titre="Porte du hall",
                description="<p>Grince.</p>",
                categorie="panne",
                statut="ouvert",
                perimetre_cible=["résidence"],
                photos_urls=[],
                fichiers_urls=[],
                saisi_pour_user_id=None,
                saisi_pour_nom=None,
                saisi_pour_email=None,
            ),
            BackgroundTasks(), session, cs,
        )

        evols = session.exec(
            select(TicketEvolution).where(TicketEvolution.ticket_id == ticket.id)
        ).all()
        assert evols == [], (
            "Un enregistrement sans aucun changement ne doit rien écrire : "
            f"{[(e.type, e.contenu) for e in evols]}"
        )

        purger_ligne(session, Ticket, ticket.id)
        session.commit()



# ── Calendrier — le Kanban EST le workflow, donc il se trace ──────────────────

def test_patch_evenement_trace_la_colonne_et_corrige_le_reste(cs):
    """Un changement de colonne est une TRANSITION ; le reste, une correction.

    Le calendrier était le dernier écran du site à faire avancer un suivi en
    silence : la colonne changeait sans que rien ne dise quand ni par qui. La
    nuance vérifiée ici est celle qui distingue les deux lignes — une transition
    porte son avant et son après, une correction n'en porte aucun.
    """
    with Session(engine) as session:
        ev = Evenement(
            titre="Ravalement bâtiment 2",
            type=TypeEvenement.travaux,
            debut=datetime(2026, 9, 1, 9, 0),
            auteur_id=cs.id,
            statut_kanban="syndic",
        )
        session.add(ev)
        session.commit()
        session.refresh(ev)

        update_evenement(
            ev.id,
            EvenementUpdate(statut_kanban="fournisseur", titre="Ravalement bâtiment 2 et 3"),
            session,
            cs,
        )

        evols = session.exec(
            select(EvenementEvolution).where(EvenementEvolution.evenement_id == ev.id)
        ).all()
        types = sorted(e.type for e in evols)
        assert types == ["commentaire", "etat"], (
            "Un changement de colonne doit laisser une TRANSITION, et le titre "
            f"corrigé une CORRECTION : trouvé {types}."
        )

        transition = next(e for e in evols if e.type == "etat")
        assert transition.ancien_statut == "syndic"
        assert transition.nouveau_statut == "fournisseur"

        correction = next(e for e in evols if e.type == "commentaire")
        assert (correction.contenu or "").startswith(PREFIXE_CORRECTION), correction.contenu
        assert "Titre" in (correction.contenu or ""), correction.contenu
        #  Une correction ne dessine AUCUN jalon de suivi : sans ces deux
        #  colonnes, le fil ne peut pas la confondre avec une étape.
        assert correction.ancien_statut is None and correction.nouveau_statut is None

        assert session.get(Evenement, ev.id).statut_kanban == "fournisseur"

        for e in evols:
            session.delete(e)
        purger_ligne(session, Evenement, ev.id)
        session.commit()


def test_patch_evenement_sans_changement_n_ecrit_rien(cs):
    """Réenregistrer les mêmes valeurs ne remplit pas l'Historique."""
    with Session(engine) as session:
        ev = Evenement(
            titre="Assemblée générale",
            type=TypeEvenement.ag,
            debut=datetime(2026, 10, 3, 18, 30),
            auteur_id=cs.id,
            statut_kanban="ag",
        )
        session.add(ev)
        session.commit()
        session.refresh(ev)

        update_evenement(
            ev.id, EvenementUpdate(titre="Assemblée générale", statut_kanban="ag"), session, cs
        )

        evols = session.exec(
            select(EvenementEvolution).where(EvenementEvolution.evenement_id == ev.id)
        ).all()
        assert evols == [], f"Aucune ligne attendue, trouvé : {[e.contenu for e in evols]}"

        purger_ligne(session, Evenement, ev.id)
        session.commit()
