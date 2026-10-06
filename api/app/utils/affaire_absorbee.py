"""Une affaire ABSORBÉE par une fusion (#1704) — ce que ses LECTEURS doivent savoir.

À part de `utils/fusion_affaires` pour le sens des dépendances : le carnet, ses
moyennes et la récidive lisent ces deux règles, et le geste de fusion importe
la visibilité, les liens, la synthèse — qui lisent le carnet. Ce module-ci ne
connaît que le modèle.

* `pas_absorbee()` : une absorbée est comptée DANS sa principale, jamais à
  côté — sinon une même panne compterait deux fois au carnet et dans les
  moyennes. 🔒 `test_fusion_affaires.py` exige qu'elle filtre chaque lecteur
  d'affaires closes.
* `ouverture_effective()` : la durée de la principale court depuis la plus
  ancienne ouverture des affaires fusionnées (arbitré le 05/10/2026).
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, col, select

from app.models.core import Ticket


def pas_absorbee():
    """La condition SQL « affaire non absorbée »."""
    return col(Ticket.fusionnee_dans_id).is_(None)


def ouverture_effective(session: Session, ticket: Ticket) -> datetime:
    """La date d'ouverture d'une affaire, absorbées comprises : la plus ancienne."""
    absorbees = session.exec(select(Ticket).where(Ticket.fusionnee_dans_id == ticket.id)).all()
    return min([ticket.cree_le, *(ouverture_effective(session, a) for a in absorbees)])
