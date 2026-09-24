"""Les anciennes adresses d'actualité — et elles seules (#1091, lot 4).

## Ce qui reste, et pourquoi

Depuis le 23/09/2026, une actualité EST une affaire de catégorie « Actualité ».
La 0210 a recopié chaque publication en affaire, et `ticket.promu_depuis_publication_id`
garde l'ancien numéro. Tout le reste du paquet — création, correction, Suite,
envois, aperçu, promotion — a été retiré : il n'en existe qu'UNE écriture, dans
`routers/tickets/` (`actualite.py` pour ce qui diffuse).

Il reste cette route, parce que des adresses ont été ENVOYÉES : chaque courriel
et chaque message WhatsApp d'une actualité portait `/actualites#pub-N`, et
l'écran les résout par `GET /publications/{N}`. Sans elle, chacun deviendrait
un lien mort. Le dépôt refuse de renommer les identifiants `TK-xxxx` pour la
même raison.

⚠️ **410 et non 404**, et la nuance porte tout l'usage : 404 dit « ça n'a
jamais existé » ; 410 dit « ça a existé, voici où c'est parti ». L'affaire est
cherchée D'ABORD : les lignes de `publication` subsistent, lues par rien
d'autre, et une publication encore présente n'en est pas moins partie.

La visibilité n'est pas décidée ici : l'écran suit la redirection vers la fiche
de l'affaire, qui applique `ticket_visible`. Le 410 ne révèle que le numéro,
pas le contenu — et seulement à un utilisateur connecté.

Verrouillé par `api/tests/test_redirection_publications.py`.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Ticket, Utilisateur
from app.utils.recuperer import ou_404

router = APIRouter(prefix="/publications", tags=["publications"])


@router.get("/{pub_id}", status_code=410)
def ou_est_partie_la_publication(
    pub_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    """L'affaire née de cette publication — ou 404 si le numéro n'a jamais existé."""
    affaire = session.exec(
        select(Ticket).where(Ticket.promu_depuis_publication_id == pub_id)
    ).first()
    if affaire is None:
        #  Le 404 passe par la porte commune (`utils/recuperer`).
        return ou_404(session, Ticket, None, "Actualité")
    raise HTTPException(
        status_code=410,
        detail={
            "message": "Cette actualité est désormais une affaire.",
            "promu_en_affaire": affaire.id,
            "numero": affaire.numero,
        },
    )


__all__ = ["router"]
