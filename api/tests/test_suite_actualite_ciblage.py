"""La Suite d'une ACTUALITÉ porte aussi son ciblage et ses options.

## Le besoin (05/09/2026, demandé à l'écran)

> « Pour Actualité, les sections "Options de publication", "Périmètre" et
>   "Destinataires" doivent être visibles même pour chaque commentaire. Tu remets
>   le dernier état pour chacun, et le nouveau sauvegardé deviendra validé. »

Une actualité vit : elle s'épingle quand elle devient urgente, se dépingle quand
elle ne l'est plus, et le moment où on la commente est précisément celui où on
s'en aperçoit. Obliger à rouvrir un autre formulaire pour cela faisait deux
gestes d'un seul.

🔴 **Le risque couvert ici est l'inverse du besoin** — c'est la leçon de
`test_evolution_perimetre.py`, et elle vaut mot pour mot : le besoin est qu'une
valeur enregistrée s'applique ; le risque est qu'un commentaire ordinaire, qui ne
parle de rien de tout cela, vienne **effacer** le ciblage de la publication. Un
`[]` envoyé au lieu d'un `None`, et l'actualité repart à « tout le monde » sans
que personne ne comprenne pourquoi.

## Depuis le 23/09/2026 (#1091, lot 4)

L'actualité est une affaire de catégorie « Actualité » : sa Suite passe par
`POST /tickets/{id}/evolutions`. Ce fichier a suivi, sans perdre un cas —
le public visé et l'Accès y ont été ajoutés, que la Suite d'une affaire ne
savait pas porter.

⚠️ Ces tests relisent la BASE après l'appel, jamais le code de retour
(`standards/04` §14 — observer la chose, pas son enregistrement).
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import RoleUtilisateur, Ticket, TicketEvolution, Utilisateur
from app.routers.tickets.evolutions import add_evolution
from app.schemas import TicketEvolutionCreate
from tests.purge_test import purger_ligne

BAT_2 = ["bat:2"]


@pytest.fixture()
def cs() -> Utilisateur:
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


def _actualite(session: Session, auteur_id: int) -> Ticket:
    t = Ticket(
        numero=f"TK-A{uuid.uuid4().hex[:6]}",
        titre="Coupure d'eau mardi",
        description="<p>De 9 h à 12 h.</p>",
        categorie="actualite",
        statut="publie",
        auteur_id=auteur_id,
        perimetre_cible=json.dumps(BAT_2, ensure_ascii=False),
        public_cible=json.dumps(["copropriétaires"], ensure_ascii=False),
        epingle=False,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _nettoyer(session: Session, ticket_id: int) -> None:
    for e in session.exec(
        select(TicketEvolution).where(TicketEvolution.ticket_id == ticket_id)
    ).all():
        session.delete(e)
    purger_ligne(session, Ticket, ticket_id)
    session.commit()


def _suite(session, cs, ticket_id, **champs):
    add_evolution(
        ticket_id,
        TicketEvolutionCreate(type="commentaire", **champs),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    session.expire_all()
    return session.get(Ticket, ticket_id)


def test_un_commentaire_ordinaire_n_efface_ni_le_ciblage_ni_les_options(cs):
    """🔴 Le cas qui casserait tout : le commentaire qui ne parle de rien.

    Il n'envoie aucun de ces champs. Rien ne doit bouger — ni le périmètre, ni le
    public visé, ni l'Accès, ni l'épinglage.
    """
    with Session(engine) as session:
        t = _actualite(session, cs.id)
        try:
            relue = _suite(session, cs, t.id, contenu="Merci pour l'info.")
            assert json.loads(relue.perimetre_cible) == BAT_2
            assert json.loads(relue.public_cible) == ["copropriétaires"]
            assert relue.epingle is False
            assert relue.reserve_perimetre is False
        finally:
            _nettoyer(session, t.id)


def test_le_ciblage_enregistre_sur_la_suite_devient_celui_de_l_actualite(cs):
    """« Le nouveau sauvegardé deviendra validé » — c'est cette phrase, testée."""
    with Session(engine) as session:
        t = _actualite(session, cs.id)
        try:
            relue = _suite(
                session,
                cs,
                t.id,
                contenu="Le bâtiment 3 est concerné aussi.",
                perimetre_cible=["bat:2", "bat:3"],
                public_cible=["copropriétaires", "locataires"],
                reserve_perimetre=True,
                epingle=True,
                urgente=True,
            )
            assert json.loads(relue.perimetre_cible) == ["bat:2", "bat:3"]
            assert json.loads(relue.public_cible) == ["copropriétaires", "locataires"]
            assert relue.reserve_perimetre is True
            assert relue.epingle is True
            assert relue.priorite == "haute"
        finally:
            _nettoyer(session, t.id)


def test_une_liste_vide_rend_l_actualite_a_tout_le_monde(cs):
    """`[]` est un effacement délibéré, `None` un silence : les deux diffèrent."""
    with Session(engine) as session:
        t = _actualite(session, cs.id)
        try:
            relue = _suite(session, cs, t.id, contenu="Finalement, pour tous.", public_cible=[])
            assert relue.public_cible is None
        finally:
            _nettoyer(session, t.id)


def test_l_invariant_d_acces_est_bien_APPELE_sur_ce_chemin(cs, monkeypatch):
    """Le chemin de la Suite n'est pas un trou dans l'invariant d'accès.

    Réserver au périmètre sur un périmètre à **portée globale** ne retirerait
    l'actualité à personne : le drapeau doit tomber, ici comme dans le `PATCH`.
    La règle vit dans `appliquer_acces` et a ses propres tests ; ce qui se
    vérifie ICI est qu'on l'appelle — c'est le branchement qui manque d'habitude.
    """
    appels: list[int] = []
    import app.routers.tickets.evolutions as module

    monkeypatch.setattr(module, "appliquer_acces", lambda ticket, session: appels.append(ticket.id))
    with Session(engine) as session:
        t = _actualite(session, cs.id)
        try:
            _suite(session, cs, t.id, contenu="Au seul bâtiment.", reserve_perimetre=True)
            assert appels == [t.id]
        finally:
            _nettoyer(session, t.id)


def test_un_resident_ne_change_pas_a_qui_l_on_parle(cs):
    """À qui l'on parle et l'Accès appartiennent au conseil — jamais à l'auteur."""
    with Session(engine) as session:
        resident = Utilisateur(
            email=f"r-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x",
            prenom="R",
            nom="S",
            role=RoleUtilisateur.résident,
        )
        session.add(resident)
        session.commit()
        session.refresh(resident)
        t = _actualite(session, resident.id)
        try:
            relue = _suite(
                session,
                resident,
                t.id,
                contenu="Pour le CS seulement ?",
                public_cible=["conseil_syndical"],
                reserve_perimetre=True,
            )
            assert json.loads(relue.public_cible) == ["copropriétaires"]
            assert relue.reserve_perimetre is False
        finally:
            _nettoyer(session, t.id)
            purger_ligne(session, Utilisateur, resident.id)
            session.commit()


def _affaire_suivie(session: Session, auteur_id: int) -> Ticket:
    t = Ticket(
        numero=f"TK-S{uuid.uuid4().hex[:6]}",
        titre="Fuite au 3e étage",
        description="<p>Sous l'évier.</p>",
        categorie="panne",
        statut="ouvert",
        auteur_id=auteur_id,
        perimetre_cible=json.dumps(BAT_2, ensure_ascii=False),
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def test_une_affaire_suivie_ne_prend_pas_de_public_vise_par_sa_suite(cs):
    """🔴 Le public visé est celui d'une ACTUALITÉ (#1091) — 25/09/2026.

    Une affaire suivie est vue de son auteur, du périmètre et du conseil ; elle
    ne s'adresse à personne d'autre (`entites/ticket.ts`, `inactivePour.suivie`).
    La Suite de l'écran l'offrait pourtant, et ce qu'on y choisissait s'ÉCRIVAIT
    sur l'affaire : une valeur qu'aucun écran ne montre, et que la correction
    efface (`chargeUtileAffaire`). L'écran ne l'offre plus ; le serveur ne
    l'écrit plus — un onglet PWA en cache peut encore l'envoyer.

    La même Suite peut, elle, rendre l'affaire URGENTE : c'est la Mise en avant,
    rouverte dans la Suite par le même lot.
    """
    with Session(engine) as session:
        t = _affaire_suivie(session, cs.id)
        try:
            relue = _suite(
                session,
                cs,
                t.id,
                contenu="La fuite s'aggrave.",
                public_cible=["locataires"],
                urgente=True,
            )
            assert relue.public_cible is None
            assert relue.priorite == "haute"
        finally:
            _nettoyer(session, t.id)
