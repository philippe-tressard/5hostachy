"""Une réponse inscrite au fil porte le TEXTE du message (05/10/2026).

`add_message` journalisait l'entrée `reponse` sans contenu : la carte de liste,
qui ne rend que l'Historique, montrait un en-tête de réponse sans corps alors que
la fiche (fil de bulles) et le courriel de notification citaient le message.

Deux gestes : l'écriture (`add_message`) et le rattrapage des entrées déjà vides
(migration 0264).
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import BackgroundTasks
from sqlmodel import select

import pytest

from app.models.core import MessageTicket, RoleUtilisateur, Ticket, TicketEvolution, Utilisateur
from app.routers.tickets import messages
from app.routers.tickets.messages_schemas import MessageCreate
from app.utils import horloge
from tests.aides_affaire import _compte, _creer, session  # noqa: F401  (fixture)
from tests.aides_base import moteur_memoire
from tests.aides_migrations import charger_migration
from tests.aides_purge import purger_ligne


@pytest.fixture()
def propre(session):  # noqa: F811
    """La base de l'application est PARTAGÉE : ce que le test y écrit en part avec lui.

    Une affaire et un compte laissés derrière ressortaient dans les tests qui
    cherchent un numéro (versement de courriels : deux affaires pour un repère).
    """
    tickets = set(session.exec(select(Ticket.id)).all())
    comptes = set(session.exec(select(Utilisateur.id)).all())
    yield session
    session.rollback()
    for modele, avant in ((Ticket, tickets), (Utilisateur, comptes)):
        for ligne_id in session.exec(select(modele.id)).all():
            if ligne_id not in avant:
                purger_ligne(session, modele, ligne_id)


def _poster(base, user, ticket_id, **champs):
    corps = MessageCreate(**champs)
    return messages.add_message(ticket_id, corps, BackgroundTasks(), session=base, user=user)


def _reponses(base, ticket_id) -> list[TicketEvolution]:
    return list(
        base.exec(
            select(TicketEvolution).where(
                TicketEvolution.ticket_id == ticket_id, TicketEvolution.type == "reponse"
            )
        ).all()
    )


def test_le_message_public_ecrit_son_texte_dans_le_fil(propre):
    auteur = _compte(propre)
    ticket = _creer(propre, auteur, categorie="panne")
    _poster(propre, auteur, ticket.id, contenu="<p>L'étiquette doit être au nom de X.</p>")
    (reponse,) = _reponses(propre, ticket.id)
    assert reponse.contenu == "<p>L'étiquette doit être au nom de X.</p>"


def test_le_message_interne_ne_livre_pas_son_texte_au_fil(propre):
    cs = _compte(propre, role=RoleUtilisateur.conseil_syndical)
    ticket = _creer(propre, cs, categorie="panne")
    _poster(propre, cs, ticket.id, contenu="Note réservée au conseil.", interne=True)
    (reponse,) = _reponses(propre, ticket.id)
    assert reponse.contenu == "Message interne"
    assert "réservée" not in (reponse.contenu or "")


def test_la_migration_rattrape_les_reponses_vides_et_seulement_elles():
    migration = charger_migration("0264")
    moteur = moteur_memoire()
    t0 = horloge.maintenant()

    with moteur.begin() as conn:
        from app.models.core import Ticket, Utilisateur
        from sqlmodel import Session

        with Session(conn) as s:
            for i in (1, 2):
                s.add(
                    Utilisateur(
                        id=i,
                        email=f"u{i}@exemple.test",
                        prenom="T",
                        nom=f"U{i}",
                        hashed_password="x",
                    )
                )
            s.add(Ticket(id=1, numero="T-1", titre="t", description="d", auteur_id=1))
            s.flush()
            #  Deux messages du même auteur, à une minute d'écart : chacun doit
            #  retrouver SON entrée. Un message interne ne doit jamais servir.
            s.add(MessageTicket(id=1, ticket_id=1, auteur_id=1, contenu="premier", cree_le=t0))
            s.add(
                MessageTicket(
                    id=2,
                    ticket_id=1,
                    auteur_id=1,
                    contenu="second",
                    cree_le=t0 + timedelta(minutes=1),
                )
            )
            s.add(
                MessageTicket(
                    id=3,
                    ticket_id=1,
                    auteur_id=2,
                    contenu="note",
                    interne=True,
                    cree_le=t0 + timedelta(minutes=2),
                )
            )
            for evol_id, auteur, decalage, contenu in (
                (1, 1, timedelta(minutes=1, milliseconds=-3), None),
                (2, 1, timedelta(milliseconds=-3), None),
                (3, 2, timedelta(minutes=2), "Message interne"),
                (4, 1, timedelta(hours=3), None),  # aucun message plausible
            ):
                s.add(
                    TicketEvolution(
                        id=evol_id,
                        ticket_id=1,
                        type="reponse",
                        contenu=contenu,
                        auteur_id=auteur,
                        cree_le=t0 + decalage,
                    )
                )
            s.commit()

        assert migration.rattraper(conn) == 2
        assert migration.rattraper(conn) == 0  # idempotente

    with moteur.connect() as conn:
        lu = dict(conn.exec_driver_sql("SELECT id, contenu FROM ticket_evolution").all())
    assert lu == {1: "second", 2: "premier", 3: "Message interne", 4: None}
