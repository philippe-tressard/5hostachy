"""Les délégations ACTIVES d'un aidant — la règle, écrite une fois (#1303).

Active = acceptée (`statut == active`), commencée, et pas terminée. Cette
condition s'écrivait deux fois — `auth/deps.get_acting_user` (agir au nom de
quelqu'un) et `utils/lecture_utilisateur` (le profil qui liste les personnes
aidées) —, et #1303 en demandait une troisième : l'aidant qui LIT ce que lit
la personne qu'il aide. Trois copies d'une condition de droit divergent sur la
borne de date au premier ajustement.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlmodel import Session, or_, select

from app.models.core import Delegation, StatutDelegation


def delegations_de_l_aidant(
    session: Session, aidant_id: int, *, mandant_id: Optional[int] = None
) -> list[Delegation]:
    """Les délégations actives aujourd'hui où `aidant_id` aide — d'un mandant
    précis si `mandant_id` est donné."""
    today = date.today()
    requete = select(Delegation).where(
        Delegation.aidant_id == aidant_id,
        Delegation.statut == StatutDelegation.active,
        Delegation.date_debut <= today,
        or_(Delegation.date_fin.is_(None), Delegation.date_fin >= today),  # type: ignore[arg-type]
    )
    if mandant_id is not None:
        requete = requete.where(Delegation.mandant_id == mandant_id)
    return list(session.exec(requete).all())
