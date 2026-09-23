"""Le calendrier n'est plus qu'une adresse — les anciens liens `#ev-N` (#1092, lot 5).

## Pourquoi il reste un routeur

Les événements sont devenus des affaires le 23/09/2026 (migration 0212) : la
page Calendrier a disparu au profit d'Affaires — le filtre « Calendrier »
(une date est définie), l'onglet Kanban. Mais des liens `/calendrier#ev-N`
dorment dans les courriels envoyés, les messages WhatsApp, les notifications
et les favoris. Un lien mort ferait croire que l'objet a disparu.

La page `/calendrier` lit le fragment `#ev-N` et demande ici où l'événement est
parti — même contrat que `GET /publications/{id}` au lot 4 :

⚠️ **410 et non 404** : 404 dit « ça n'a jamais existé » ; 410 dit « ça a
existé, voici où c'est parti ». La visibilité n'est pas décidée ici : l'écran
suit la redirection vers la fiche de l'affaire, qui applique `ticket_visible`.
Le 410 ne révèle que le numéro, et seulement à un utilisateur connecté.

Verrouillé par `api/tests/test_redirection_evenements.py`.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Ticket, Utilisateur
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/calendrier", tags=["calendrier"])


@router.get("/{ev_id}", status_code=410)
def ou_est_parti_l_evenement(
    ev_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    """L'affaire née de cet événement — ou 404 si le numéro n'a jamais existé."""
    affaire = session.exec(
        select(Ticket).where(Ticket.promu_depuis_evenement_id == ev_id)
    ).first()
    if affaire is None:
        return ou_404(session, Ticket, None, "Événement")
    raise HTTPException(
        status_code=410,
        detail={
            "message": "Cet événement est désormais une affaire.",
            "promu_en_affaire": affaire.id,
            "numero": affaire.numero,
        },
    )


__all__ = ["router"]
