"""Les AFFAIRES LIÉES (#1342) — réciproques, et un lien ne révèle rien.

Ce que ce fichier éprouve, dans l'ordre de ce qui coûterait le plus cher :

1. une affaire que le lecteur ne peut pas lire n'apparaît PAS dans ses liens,
   ni dans le choix proposé — et la désigner par son numéro est refusé comme si
   elle n'existait pas ;
2. corriger ses liens ne défait pas ceux qu'on ne voit pas ;
3. le lien est réciproque ; une Suite ajoute sans retirer ; une affaire
   supprimée ne laisse aucun lien.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.affaires_liees import AffaireLiee
from app.models.core import StatutTicket, Ticket, Utilisateur
from app.routers.tickets.commun import ticket_read
from app.routers.tickets.mise_a_jour import update_ticket
from app.schemas import TicketUpdate
from app.utils.affaires_liees import (
    ajouter_liens,
    choix_lisibles,
    ids_lies,
    poser_liens,
    supprimer_liens_de,
)
from tests.purge_test import purger_ligne


def _utilisateur(session, roles: str) -> Utilisateur:
    u = Utilisateur(
        email=f"{roles}-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x",
        prenom="Camille",
        nom="Sorel",
        roles_json=roles,
        actif=True,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _affaire(session, auteur, titre, confidentiel=False) -> Ticket:
    t = Ticket(
        numero=f"T-{uuid.uuid4().hex[:6]}",
        titre=titre,
        description="…",
        categorie="panne",
        auteur_id=auteur.id,
        statut=StatutTicket.ouvert,
        confidentiel=confidentiel,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


@pytest.fixture()
def contexte():
    """Trois affaires d'un résident, et une confidentielle d'un autre."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        auteur = _utilisateur(session, "résident")
        autre = _utilisateur(session, "résident")
        cs = _utilisateur(session, "conseil_syndical")
        a = _affaire(session, auteur, "Fuite au 3e")
        b = _affaire(session, auteur, "Tache au plafond du 2e")
        c = _affaire(session, auteur, "Colonne d'eau")
        secrete = _affaire(session, autre, "Litige de voisinage", confidentiel=True)
        yield session, (a, b, c, secrete), auteur, cs
        for t in (a, b, c, secrete):
            supprimer_liens_de(session, t.id)
        session.commit()
        for t in (a, b, c, secrete):
            purger_ligne(session, Ticket, t.id)
        for u in (auteur, autre, cs):
            purger_ligne(session, Utilisateur, u.id)
        session.commit()


def _ids(lues):
    return [lue.id for lue in lues]


def test_le_lien_est_reciproque_et_rappelle_le_titre(contexte):
    session, (a, b, _c, _s), auteur, _cs = contexte
    poser_liens(session, a, [b.id], auteur)
    session.commit()
    vue_de_b = ticket_read(b, session, auteur).affaires_liees
    assert _ids(vue_de_b) == [a.id]
    assert vue_de_b[0].titre == "Fuite au 3e"
    assert vue_de_b[0].numero == a.numero


def test_sans_lecteur_aucun_lien_nest_rendu(contexte):
    """Le défaut sûr : une réponse qui ne sait pas à qui elle parle ne montre rien."""
    session, (a, b, _c, _s), auteur, _cs = contexte
    poser_liens(session, a, [b.id], auteur)
    session.commit()
    assert ticket_read(a, session).affaires_liees == []


def test_une_affaire_illisible_napparait_pas(contexte):
    """Le CS lie une affaire confidentielle : le résident n'en voit RIEN."""
    session, (a, _b, _c, secrete), auteur, cs = contexte
    poser_liens(session, a, [secrete.id], cs)
    session.commit()
    assert _ids(ticket_read(a, session, cs).affaires_liees) == [secrete.id]
    assert ticket_read(a, session, auteur).affaires_liees == []


def test_le_choix_ne_propose_que_ce_quon_peut_lire(contexte):
    session, (a, b, c, secrete), auteur, cs = contexte
    proposes = {lue["id"] for lue in choix_lisibles(session, auteur)}
    assert {a.id, b.id, c.id} <= proposes
    assert secrete.id not in proposes
    assert secrete.id in {lue["id"] for lue in choix_lisibles(session, cs)}


def test_designer_une_affaire_illisible_est_refuse_comme_une_absente(contexte):
    """Même réponse pour « confidentielle » et « inexistante » : rien ne fuit."""
    session, (a, _b, _c, secrete), auteur, _cs = contexte
    with pytest.raises(HTTPException) as illisible:
        poser_liens(session, a, [secrete.id], auteur)
    with pytest.raises(HTTPException) as absente:
        poser_liens(session, a, [10**9], auteur)
    assert illisible.value.status_code == absente.value.status_code == 422
    assert "introuvable" in illisible.value.detail


def test_corriger_ne_defait_pas_ce_quon_ne_voit_pas(contexte):
    session, (a, b, _c, secrete), auteur, cs = contexte
    poser_liens(session, a, [b.id, secrete.id], cs)
    session.commit()
    #  Le résident retire tout ce qu'il voit…
    update_ticket(
        a.id, TicketUpdate(affaires_liees=[]), BackgroundTasks(), session=session, user=auteur
    )
    #  … et le lien confidentiel posé par le conseil survit.
    assert ids_lies(session, a.id) == {secrete.id}


def test_une_correction_sans_la_section_ne_touche_a_rien(contexte):
    session, (a, b, _c, _s), auteur, _cs = contexte
    poser_liens(session, a, [b.id], auteur)
    session.commit()
    update_ticket(
        a.id,
        TicketUpdate(titre="Fuite au 3e étage"),
        BackgroundTasks(),
        session=session,
        user=auteur,
    )
    assert ids_lies(session, a.id) == {b.id}


def test_une_suite_ajoute_sans_retirer(contexte):
    session, (a, b, c, _s), auteur, _cs = contexte
    poser_liens(session, a, [b.id], auteur)
    ajouter_liens(session, a, [c.id], auteur)
    session.commit()
    assert ids_lies(session, a.id) == {b.id, c.id}


def test_se_lier_a_soi_meme_et_les_doublons_sont_ignores(contexte):
    session, (a, b, _c, _s), auteur, _cs = contexte
    poser_liens(session, a, [a.id, b.id, b.id], auteur)
    ajouter_liens(session, b, [a.id], auteur)  # le même lien, vu de l'autre bout
    session.commit()
    lignes = session.exec(select(AffaireLiee).where(AffaireLiee.affaire_id.in_([a.id, b.id]))).all()
    assert len(lignes) == 1


def test_une_affaire_supprimee_ne_laisse_aucun_lien(contexte):
    session, (a, b, c, _s), auteur, _cs = contexte
    poser_liens(session, a, [b.id, c.id], auteur)
    session.commit()
    supprimer_liens_de(session, a.id)
    session.commit()
    assert ids_lies(session, b.id) == set()
    assert ids_lies(session, c.id) == set()
