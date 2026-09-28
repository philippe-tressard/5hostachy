"""Le message d'une Suite sur le groupe de la résidence — composé UNE fois.

## Pourquoi

Une Suite annonce ce qui vient de se passer : c'est **son** message qui part,
jamais celui qui a ouvert l'affaire (28/09/2026, signalé par l'utilisateur).
Trois endroits le composaient chacun à sa façon :

- la Suite d'une **affaire** (`evolutions.py`) ne rappelait le lien qu'à partir
  du deuxième commentaire — la première Suite partait sans adresse, alors que le
  message initial est déjà de l'historique ;
- la Suite d'une **actualité** (`actualite.py`) écrivait le lien dans le texte ET
  le passait au canal, qui l'ajoute à son tour : deux fois la même adresse ;
- l'**aperçu** (`apercu.py`) montrait la description de l'affaire — le message
  initial — au lieu de la Suite saisie. On regarde l'aperçu pour vérifier : il
  mentait sur la seule chose qu'on venait d'écrire.

## Ce que ce module rend

Le titre, le texte (le message en cours, suivi du rappel de l'historique) et le
lien de la fiche, que le canal place après le texte (`construire_message`). Le
lien est donc TOUJOURS là, y compris dans le message restreint d'une actualité
ciblée, qui ne porte que lui.

🔒 `test_suite_groupe.py` : les deux envois et l'aperçu passent par ici.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.core import Ticket, TicketEvolution
from app.utils.categories_ticket import ticket_urgent
from app.utils.liens import lien_ticket
from app.utils.nature_affaire import est_actualite


@dataclass(frozen=True)
class MessageSuite:
    titre: str
    contenu: str
    lien: str
    urgente: bool


def _paroles_precedentes(session: Session, ticket: Ticket, *, suite_enregistree: bool) -> int:
    """Le message initial, plus chaque parole du fil avant la Suite.

    `suite_enregistree` : à l'envoi, la Suite est déjà en base et c'est la
    dernière du fil — elle ne se compte pas elle-même. À l'aperçu, elle n'existe
    pas encore.
    """
    evols = session.exec(
        select(TicketEvolution)
        .where(TicketEvolution.ticket_id == ticket.id)
        .order_by(TicketEvolution.cree_le)
    ).all()
    if suite_enregistree and evols:
        evols = evols[:-1]
    return 1 + sum(1 for e in evols if e.contenu)


def message_suite(
    session: Session,
    ticket: Ticket,
    contenu: str,
    *,
    site_url: str,
    suite_enregistree: bool,
) -> MessageSuite:
    """Ce que le groupe reçoit pour une Suite : son message, et où lire le reste.

    `site_url` : déjà passée par `base_site` chez l'appelant (`test_base_site`).
    """
    titre = f"{ticket.titre} (suite)" if est_actualite(ticket) else f"🔧 {ticket.titre}"
    n = _paroles_precedentes(session, ticket, suite_enregistree=suite_enregistree)
    rappel = (
        f"📜 Déjà {n} message(s) dans cet échange, message initial compris : "
        "l'historique complet est sur l'application."
    )
    return MessageSuite(
        titre=titre,
        contenu=f"{contenu}\n\n{rappel}" if contenu else rappel,
        lien=site_url + lien_ticket(ticket.id),
        #  La règle de la création, pour les deux natures : la Suite d'une
        #  affaire partait sans l'urgence que son aperçu annonçait.
        urgente=ticket_urgent(ticket),
    )
