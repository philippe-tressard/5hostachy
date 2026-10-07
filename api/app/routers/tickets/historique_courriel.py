"""Tickets — l'historique que porte un courriel, et les affaires liées qui le prolongent.

Sorti de `courriels.py` le 05/10/2026 : le tableau d'historique de `ticket_syndic`
s'écrivait là, et lui ajouter les affaires liées l'aurait grossi pour un sujet qui
a sa propre règle.

## Ce que le courriel dit d'un lien entre deux affaires

1. **L'historique de l'affaire trace le lien** : une ligne datée du jour où le
   conseil l'a posé — « Liée à l'affaire #TK-… — titre » —, rangée parmi les
   évolutions dans l'ordre du temps.
2. **Sous l'historique, chaque affaire liée avec le sien**, de la plus ancienne
   à la plus récente (date de CRÉATION de l'affaire, et non du lien : c'est
   l'ordre dans lequel les faits se sont produits).

## 🔴 Ce qui n'y va jamais

Une affaire liée **réservée au conseil** (`reservee_au_conseil` : confidentielle,
Destinataires « Conseil syndical » seul, ou fermée par sa catégorie) ne paraît
ni dans la trace ni dans le bloc. Le destinataire est le syndic — hors de la
copropriété — et la règle dit déjà qu'« aucun courriel » n'en part : un lien ne
donne pas le droit d'en dire le titre ni le fil par la bande. Le conseil a décidé
d'envoyer CETTE affaire, pas celle à laquelle il l'a rattachée.
"""

from __future__ import annotations

from typing import Iterable

from pydantic import NaiveDatetime
from sqlmodel import Session, select

from app.models.core import Ticket, TicketEvolution
from app.utils.affaires_liees import liens_de
from app.utils.dates_fr import date_courte, datetime_longue_paris as fmt_paris
from app.utils.visibility import reservee_au_conseil

from .commun import libelle_evolution


def affaires_liees_du_courriel(
    session: Session, ticket: Ticket
) -> list[tuple[Ticket, NaiveDatetime]]:
    """Les affaires liées que le courriel peut montrer, avec la date de chaque lien.

    De la plus ancienne à la plus récente (création de l'affaire, puis `id`
    pour départager deux affaires déposées à la même seconde). Un ticket non
    persisté — l'aperçu d'une création — n'a aucun lien.
    """
    if ticket.id is None:
        return []
    liens = liens_de(session, ticket.id)
    if not liens:
        return []
    liees = session.exec(select(Ticket).where(Ticket.id.in_(liens))).all()
    montrables = [t for t in liees if not reservee_au_conseil(t)]
    montrables.sort(key=lambda t: (t.cree_le, t.id))
    return [(t, liens[t.id]) for t in montrables]


def lignes_historique(
    ticket: Ticket,
    evolutions: Iterable[TicketEvolution] = (),
    liees: Iterable[tuple[Ticket, NaiveDatetime]] = (),
) -> list[dict]:
    """Les lignes `{date, label}` de l'historique : création, évolutions, liens.

    Rangées par date. Le tri est stable : à égalité, la création passe avant
    l'évolution, et l'évolution avant le lien qu'elle a pu provoquer.
    """
    entrees: list[tuple[NaiveDatetime, dict]] = [
        (ticket.cree_le, {"date": date_courte(ticket.cree_le), "label": "Création du ticket"})
    ]
    for ev in evolutions:
        entrees.append(
            (
                ev.cree_le,
                {"date": fmt_paris(ev.cree_le), "label": libelle_evolution(ev, avec_extrait=True)},
            )
        )
    for liee, le in liees:
        entrees.append(
            (
                le,
                {"date": fmt_paris(le), "label": f"Liée à l’affaire #{liee.numero} — {liee.titre}"},
            )
        )
    entrees.sort(key=lambda e: e[0])
    return [ligne for _, ligne in entrees]


def contexte_affaires_liees(
    session: Session, liees: Iterable[tuple[Ticket, NaiveDatetime]]
) -> list[dict]:
    """Le bloc `affaires_liees` du modèle : chaque affaire avec SON historique."""
    bloc = []
    for liee, _le in liees:
        evolutions = session.exec(
            select(TicketEvolution)
            .where(TicketEvolution.ticket_id == liee.id)
            .order_by(TicketEvolution.cree_le)
        ).all()
        bloc.append(
            {
                "numero": liee.numero,
                "titre": liee.titre,
                "date_creation": date_courte(liee.cree_le),
                "historique": lignes_historique(liee, evolutions),
            }
        )
    return bloc
