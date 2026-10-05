"""Les courriels reçus à l'adresse des affaires — ce que la relève en a fait.

Espace CS › Courriels. Une ligne par message traité (`utils/courriel_journal`),
les plus récents d'abord, dans la limite du paramètre du site.

## Qui lit quoi (05/10/2026)

Le conseil syndical et l'administration — c'est le conseil qui transfère les
messages, c'est lui qui doit voir qu'un transfert n'est pas entré. Mais l'adresse
d'un expéditeur est une donnée personnelle : **l'administrateur la lit en entier,
le conseil n'en lit que le nom**. Le journal était réservé à l'admin pour cette
raison ; ouvrir la lecture ne doit pas ouvrir l'adresse.

⚠️ Jamais le corps du message : le journal dit ce qui a été DÉCIDÉ, le texte vit
dans le fil de l'affaire ou dans la boîte de réception.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import RoleUtilisateur, Utilisateur
from app.utils.courriel_journal import (
    derniers_releves,
    nom_de_l_expediteur,
    nombre_affiche,
)

router = APIRouter(prefix="/courriels-affaires", tags=["courriels-affaires"])


class CourrielReleveRead(BaseModel):
    """Une ligne du journal des relèves — propre à cet écran, donc déclarée ici."""

    id: int
    releve_le: datetime
    envoye_le: datetime | None = None
    #: L'adresse en entier pour l'administrateur, le nom seul pour le conseil.
    expediteur: str
    objet: str
    decision: str
    motif: str
    ticket_id: int | None = None
    affaire: str | None = None


class JournalCourriels(BaseModel):
    #: Le paramètre du site : combien de messages l'écran en montre au plus.
    limite: int
    messages: list[CourrielReleveRead]


@router.get("", response_model=JournalCourriels)
def courriels_affaires(
    user: Utilisateur = Depends(require_cs_or_admin),
    session: Session = Depends(get_session),
):
    """Ce que la relève a fait des derniers messages, et pourquoi (#1447).

    Les IGNORE y figurent — c'est eux qui étaient muets.
    """
    voit_l_adresse = user.has_role(RoleUtilisateur.admin)
    messages = []
    for r in derniers_releves(session):
        ligne = CourrielReleveRead.model_validate(r, from_attributes=True)
        if not voit_l_adresse:
            ligne.expediteur = nom_de_l_expediteur(r.expediteur)
        messages.append(ligne)
    return JournalCourriels(limite=nombre_affiche(session), messages=messages)
