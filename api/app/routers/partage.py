"""TRANSMETTRE un lien par courriel — le 🔗 qui propose l'envoi (#1357).

Option E des maquettes du 26/09/2026 : le clic sur 🔗 copie le lien, puis le
message « Lien copié » propose « L'envoyer par courriel ». D'abord pour les
affaires ; puis, le même jour : *« dans tous les cas, si celui-ci n'a pas les
droits, il ne verra rien »* — pour TOUT objet qui porte un 🔗.

## Deux courriels, une route

- **Une affaire** (`ticket`) : son titre et son numéro partent (`ticket_partage`),
  parce qu'on sait vérifier que l'expéditeur la LIT (`ticket_visible`, même
  refus que sa fiche) — sans quoi il ferait fuiter un titre qu'il ne voit pas.
- **Tout autre objet** (`utils/liens.OBJETS_TRANSMISSIBLES`) : ce qu'il est et
  son lien, sans titre (`lien_partage`). Le lien est reconstruit du type et de
  l'identifiant — jamais un chemin ni un texte venus de l'écran —, il ne mène
  donc qu'à une page de ce site, qui décide seule de ce que voit le lecteur.

## Ce qui tient pour les deux

- **Plafonnée** (`LIMITE_PARTAGE_COURRIEL`) : sans quoi le site devient un relais
  d'expédition vers des adresses choisies par l'appelant.
- **Tracée sans l'adresse** : qui, quoi — jamais le destinataire, donnée
  personnelle d'un tiers qui n'a rien demandé.
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
from app.utils.liens import OBJETS_TRANSMISSIBLES, lien_transmissible
from app.utils.noms import contexte_personne
from app.utils.recuperer import ou_404
from app.utils.visibility import ticket_visible

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/partage", tags=["partage"])


class PartageCourriel(BaseModel):
    #  `ticket`, ou une clé de `OBJETS_TRANSMISSIBLES`.
    objet: str
    id: int
    email: EmailStr


@router.post("", status_code=204)
@limiter.limit(LIMITE_PARTAGE_COURRIEL)
def partager_par_courriel(
    request: Request,
    body: PartageCourriel,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    from app.utils.email import send_email

    #  Les clés restent LITTÉRALES à chaque envoi : `test_email_contexte_appel`
    #  lit le contexte au point d'appel, et ne voit pas au travers d'un dict bâti avant.
    site = contexte_site(config_site(session))
    if body.objet == "ticket":
        ticket = ou_404(session, Ticket, body.id, "Affaire")
        if not ticket_visible(ticket, user):
            raise HTTPException(403, "Accès refusé")
        background_tasks.add_task(
            send_email,
            code="ticket_partage",
            to=str(body.email),
            context={
                "ticket": {"id": ticket.id, "numero": ticket.numero, "titre": ticket.titre},
                "auteur_action": contexte_personne(user),
                **site,
            },
        )
    elif body.objet in OBJETS_TRANSMISSIBLES:
        background_tasks.add_task(
            send_email,
            code="lien_partage",
            to=str(body.email),
            context={
                "objet": {
                    "quoi": OBJETS_TRANSMISSIBLES[body.objet],
                    "lien": lien_transmissible(body.objet, body.id),
                },
                "auteur_action": contexte_personne(user),
                **site,
            },
        )
    else:
        raise HTTPException(422, "Cet objet ne se transmet pas par courriel.")
    logger.info(
        "Lien %s-%s transmis par courriel par l'utilisateur %s", body.objet, body.id, user.id
    )
