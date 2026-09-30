"""La liste des tickets suit l'ACTIVITÉ, pas la date de dépôt.

## Le besoin (05/09/2026, demandé à l'écran)

> « s'il y a eu un commentaire sur un ticket, celui-ci remonte dans la liste des
>   tickets de la page tickets (tri sur mise à jour sauf édition pour une
>   correction) »

Un dossier qui bouge doit se voir. Trié sur `cree_le`, un ticket ouvert il y a
trois mois et commenté ce matin restait en bas de la liste, là où personne ne le
relit.

## 🔴 Ce que ces tests protègent vraiment

La moitié facile est « un commentaire fait remonter ». La moitié qui coûte est
l'exclusion : **une correction ne doit rien faire remonter**. C'est pourquoi le
tri ne peut pas se faire sur `mis_a_jour_le`, qui bouge à chaque écriture — y
compris pour une faute de frappe. Corriger un titre remettrait le ticket en tête
sans qu'il se soit rien passé.

C'est la même distinction que l'archivage, qui se mesure sur `statut_change_le`
et jamais sur `mis_a_jour_le` (`ux-patterns` §16) : une colonne par question.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlmodel import Session

from app.database import engine
from app.models.core import (
    Ticket,
    TicketEvolution,
)
from app.routers.tickets.crud import list_tickets
from app.utils import horloge
from tests.aides_fil import cs, nettoyer_affaires  # noqa: F401


def _ticket(session: Session, auteur_id: int, titre: str, cree_le: datetime) -> Ticket:
    t = Ticket(
        numero=f"TK-{uuid.uuid4().hex[:6].upper()}",
        titre=titre,
        description="<p>…</p>",
        categorie="panne",
        statut="ouvert",
        auteur_id=auteur_id,
        cree_le=cree_le,
        mis_a_jour_le=cree_le,
    )
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def _rang(liste, numero: str) -> int:
    return [t.numero for t in liste].index(numero)


def test_un_ticket_commente_remonte_au_dessus_d_un_ticket_plus_recent(cs):
    """Le besoin, dans sa forme la plus nue."""
    now = horloge.maintenant()
    with Session(engine) as session:
        vieux = _ticket(session, cs.id, "Fuite ancienne", now - timedelta(days=90))
        recent = _ticket(session, cs.id, "Demande récente", now - timedelta(days=1))
        try:
            session.add(
                TicketEvolution(
                    ticket_id=vieux.id,
                    type="commentaire",
                    contenu="Le plombier passe jeudi.",
                    auteur_id=cs.id,
                    cree_le=now,
                )
            )
            session.commit()

            liste = list_tickets(session=session, user=cs)
            assert _rang(liste, vieux.numero) < _rang(liste, recent.numero), (
                "un ticket commenté ce matin doit passer devant un ticket déposé hier"
            )
        finally:
            nettoyer_affaires(session, vieux.id, recent.id)


def test_une_correction_ne_fait_RIEN_remonter(cs):
    """🔴 La moitié qui coûte, et la raison pour laquelle `mis_a_jour_le` ne convient pas.

    Corriger une faute de frappe touche `mis_a_jour_le` sans rien apporter au
    dossier. Le ticket doit rester où il est.
    """
    now = horloge.maintenant()
    with Session(engine) as session:
        vieux = _ticket(session, cs.id, "Fuite ancienne", now - timedelta(days=90))
        recent = _ticket(session, cs.id, "Demande récente", now - timedelta(days=1))
        try:
            #  Exactement ce que fait le `PATCH` d'une correction pure : il touche
            #  `mis_a_jour_le`, et n'écrit AUCUNE entrée dans le fil.
            vieux.titre = "Fuite ancienne (corrigé)"
            vieux.mis_a_jour_le = now
            session.add(vieux)
            session.commit()

            liste = list_tickets(session=session, user=cs)
            assert _rang(liste, recent.numero) < _rang(liste, vieux.numero), (
                "une correction ne doit pas remonter un ticket : rien ne s'est passé "
                "sur le dossier, seul son libellé a changé"
            )
        finally:
            nettoyer_affaires(session, vieux.id, recent.id)


def test_relire_une_entree_ne_reordonne_pas_le_fil(cs):
    """Éditer un commentaire ne change pas sa date de création — donc pas le rang.

    Sans cela, se relire ferait remonter le dossier, et la liste raconterait
    l'activité de celui qui corrige plutôt que celle du dossier.
    """
    now = horloge.maintenant()
    with Session(engine) as session:
        vieux = _ticket(session, cs.id, "Fuite ancienne", now - timedelta(days=90))
        recent = _ticket(session, cs.id, "Demande récente", now - timedelta(days=1))
        try:
            evol = TicketEvolution(
                ticket_id=vieux.id,
                type="commentaire",
                contenu="Premier jet.",
                auteur_id=cs.id,
                cree_le=now - timedelta(days=60),
            )
            session.add(evol)
            session.commit()
            session.refresh(evol)

            #  Une entrée n'a PAS de `mis_a_jour_le` : éditer ne réécrit que son
            #  contenu. C'est ce qui rend le rang stable — il n'y a même pas de
            #  date à confondre avec celle de création.
            evol.contenu = "Premier jet, relu."
            session.add(evol)
            session.commit()

            liste = list_tickets(session=session, user=cs)
            assert _rang(liste, recent.numero) < _rang(liste, vieux.numero), (
                "relire une entrée vieille de deux mois ne la rend pas récente"
            )
        finally:
            nettoyer_affaires(session, vieux.id, recent.id)
