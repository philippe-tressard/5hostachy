"""L'assistant IA côté formulaires — l'usage « description » (#985).

Deux points d'accès, tous deux réservés au conseil syndical et à
l'administration : l'appel est facturé, et c'est l'arbitrage du 17/09/2026
(*« réservé au CS car payant »*). L'écran n'affiche l'icône ✨ qu'à eux ; le
serveur refuse aux autres, ce que l'interface masque n'étant qu'un confort
(`standards/03` §1).

⚠️ La synthèse de contrat, elle, garde sa route dans `prestataires.py` : elle
part d'un contrat en base, celle-ci part d'un texte en cours de saisie.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.core import Utilisateur
from app.utils.assistant_description import Demande, disponible, retravailler
from app.utils.llm import ErreurLLM

router = APIRouter(prefix="/assistant", tags=["assistant"])


class DemandeDescription(BaseModel):
    """Ce que la section Description envoie — voir `utils/assistant_description`."""

    entite: str = Field(min_length=1, max_length=80)
    titre: Optional[str] = None
    description: Optional[str] = None
    #: Des libellés courts, déclarés par l'écran : catégorie, périmètre, état…
    contexte: dict[str, str] = {}
    precision: Optional[str] = None
    #: Faux sur une entrée de fil — un commentaire n'a pas de titre à proposer.
    avec_titre: bool = True


class PropositionDescription(BaseModel):
    titre: Optional[str] = None
    description: str
    titre_modifie: bool
    description_modifiee: bool


@router.get("/disponible")
def assistant_disponible(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
) -> dict[str, bool]:
    """L'icône ✨ a-t-elle un sens sur les formulaires ? — décidé par le serveur.

    Un booléen par usage de formulaire ; un seul aujourd'hui. Rien de la
    configuration ne sort : ni le fournisseur, ni le modèle, ni le prompt.
    """
    return {"description": disponible(session)}


@router.post(
    "/description",
    response_model=PropositionDescription,
    summary="Retravailler un titre et une description (CS/Admin)",
)
async def proposer_description(
    body: DemandeDescription,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Rend une PROPOSITION. N'enregistre rien.

    🔴 Le geste est manuel : rien n'appelle ce point d'entrée sinon l'icône ✨
    de la section Description, cliquée par un membre du conseil syndical. Il se
    rejoue autant de fois que l'auteur le veut, chaque appel partant du texte
    COURANT du formulaire.
    """
    try:
        p = await retravailler(
            session,
            Demande(
                entite=body.entite,
                titre=body.titre,
                description=body.description,
                contexte=body.contexte,
                precision=body.precision,
                avec_titre=body.avec_titre,
            ),
        )
    except ErreurLLM as exc:
        raise HTTPException(400, str(exc))
    return PropositionDescription(
        titre=p.titre,
        description=p.description,
        titre_modifie=p.titre_modifie,
        description_modifiee=p.description_modifiee,
    )
