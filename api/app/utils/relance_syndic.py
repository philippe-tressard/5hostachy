"""Quelles affaires se relancent auprès du syndic — la règle, écrite une fois.

**Toutes, sauf les résolues, les annulées, les supprimées et les archivées — sans
exception** (arbitré par l'utilisateur le 10/10/2026). La catégorie « bug » et
le marquage « non relançable » en écartaient d'autres : ils ne comptent plus, et
le geste a quitté l'écran.

Elle était écrite deux fois : dans la liste de l'Espace CS (Reporting → Relance
syndic) et dans le compteur « N affaires syndic à relancer » du tableau de bord,
avec chacune son délai par défaut — et le compteur ne retenait que les affaires
déjà adressées au syndic. Aucune n'excluait une affaire 📦 archivée par le
conseil, ni une affaire absorbée par une fusion (close avec sa principale).

La liste, le compteur, l'envoi et les réponses du syndic la lisent ici.
Une affaire SUPPRIMÉE n'existe plus en base : aucune requête ne la ramène.
"""

from __future__ import annotations

from sqlmodel import Session, col, select

from app.models.core import STATUTS_TICKET_ACTIFS, ConfigSite, Ticket
from app.utils.affaire_absorbee import pas_absorbee

#: Délai par défaut, en jours, sans avancée avant qu'une affaire soit éligible.
DELAI_DEFAUT_J = 30


def delai_relance_jours(session: Session) -> int:
    """Le délai réglé par l'administrateur (`relance_syndic_delai_jours`), sinon 30."""
    cfg = session.exec(
        select(ConfigSite).where(ConfigSite.cle == "relance_syndic_delai_jours")
    ).first()
    return int(cfg.valeur) if cfg else DELAI_DEFAUT_J


def conditions_relancable() -> tuple:
    """Les conditions SQL « affaire à relancer »."""
    return (
        #  ACTIFS, pas « non clos » : une actualité (`publie`) n'est pas une
        #  affaire suivie — elle n'a ni cycle ni syndic à relancer (#1091).
        col(Ticket.statut).in_(STATUTS_TICKET_ACTIFS),
        ~col(Ticket.archive_manuel),
        pas_absorbee(),
    )


def ids_relancables(session: Session, ids: set[int]) -> set[int]:
    """Parmi `ids`, ceux que la règle admet encore."""
    if not ids:
        return set()
    return set(
        session.exec(
            select(Ticket.id).where(col(Ticket.id).in_(ids), *conditions_relancable())
        ).all()
    )
