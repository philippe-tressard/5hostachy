"""TRANSMETTRE une affaire par courriel — le 🔗 qui propose l'envoi (#1357).

Option E des maquettes du 26/09/2026 : le clic sur 🔗 copie le lien, puis le
message de confirmation propose « L'envoyer par courriel ». Cette route fait
partir ce courriel.

## Ce qui la tient

- **Lire, c'est pouvoir transmettre.** Qui ne lit pas l'affaire reçoit le même
  refus que sur sa fiche (`crud.get_ticket`, 403) : il ne transmet que ce qu'il voit.
- **Rien ne sort que le titre, le numéro et le lien** (`ticket_partage`). Le
  lien n'ouvre aucun droit : le destinataire se connecte, et `ticket_visible`
  décide pour lui.
- **Plafonnée** (`LIMITE_PARTAGE_COURRIEL`) : sans quoi le site devient un relais
  d'expédition vers des adresses choisies par l'appelant.
- **Tracée sans l'adresse** : qui, quelle affaire — jamais le destinataire, une
  donnée personnelle d'un tiers qui n'a rien demandé.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Ticket, Utilisateur
from app.utils.config_site import config_site, contexte_site
from app.utils.limiter import LIMITE_PARTAGE_COURRIEL, limiter
from app.utils.noms import contexte_personne
from app.utils.recuperer import ou_404
from app.utils.visibility import ticket_visible

logger = logging.getLogger(__name__)
router = APIRouter()


class PartageCourriel(BaseModel):
    email: EmailStr


@router.post("/{ticket_id}/partager", status_code=204)
@limiter.limit(LIMITE_PARTAGE_COURRIEL)
def partager_par_courriel(
    request: Request,
    ticket_id: int,
    body: PartageCourriel,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    ticket = ou_404(session, Ticket, ticket_id, "Affaire")
    if not ticket_visible(ticket, user):
        raise HTTPException(403, "Accès refusé")
    from app.utils.email import send_email

    background_tasks.add_task(
        send_email,
        code="ticket_partage",
        to=str(body.email),
        context={
            "ticket": {"id": ticket.id, "numero": ticket.numero, "titre": ticket.titre},
            "auteur_action": contexte_personne(user),
            **contexte_site(config_site(session)),
        },
    )
    logger.info("Affaire %s transmise par courriel par l'utilisateur %s", ticket.id, user.id)
