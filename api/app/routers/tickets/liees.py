"""Le CHOIX des affaires à lier (#1342) — la liste que la section « Affaires
liées » propose.

Un routeur à part, et non une route de `crud` : son chemin est LITTÉRAL
(`/tickets/choix`), et monté après `crud`, `/{ticket_id}` le capterait — la
route répondrait 422 sans qu'aucune erreur ne le dise (cf. `__init__.py`).

Il rend numéro, titre et statut, rien d'autre : de quoi reconnaître une affaire
dans la liste, sans charger les fiches complètes.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Utilisateur
from app.schemas import AffaireLieeLue
from app.utils.affaires_liees import choix_lisibles

router = APIRouter()


@router.get("/choix", response_model=list[AffaireLieeLue])
def choix_affaires(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    return choix_lisibles(session, user)
