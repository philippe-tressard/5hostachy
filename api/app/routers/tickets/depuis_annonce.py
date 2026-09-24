"""Pré-remplir une actualité depuis une affiche de hall (#832).

Le miroir de `annonces_hall.prefill_depuis_element` : le conseil compose souvent
l'affiche du hall d'abord, puis veut la même information en ligne. Déplacé de
`routers/publications/` le 23/09/2026 — une actualité est une affaire de
catégorie « Actualité » (#1091, lot 4), elle se crée par `POST /tickets`.

Aucune écriture : le conseil ajuste ensuite librement avant de publier.

⚠️ **Aucun lien n'est conservé vers l'affiche d'origine**, contrairement au sens
inverse qui garde `ticket_id`. Là-bas le lien SERT — c'est lui qui donne son URL
au message WhatsApp de l'affiche. Ici rien ne le lirait, et une colonne que
personne n'interroge devient une seconde vérité sur « d'où vient ce texte ».
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.deps import require_cs_or_admin
from app.database import get_session
from app.models.annonce_hall import AnnonceHall
from app.models.core import Utilisateur
from app.utils.perimetres import parse_json_perimetres
from app.utils.photos import parse_photos
from app.utils.recuperer import ou_404

router = APIRouter()


@router.get(
    "/depuis-annonce-hall/{annonce_id}",
    summary="Pré-remplissage d'une actualité depuis une annonce de hall (CS/Admin)",
)
def prefill_depuis_annonce_hall(
    annonce_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    """Les champs d'une affiche, dans le vocabulaire de l'affaire qu'ils alimentent."""
    annonce = ou_404(session, AnnonceHall, annonce_id, "Annonce de hall")
    return {
        "titre": annonce.titre,
        "description": annonce.message,
        "perimetre_cible": parse_json_perimetres(annonce.perimetre_cible),
        #  Les images de l'affiche sont déjà des URLs de notre volume : elles se
        #  reprennent telles quelles, sans re-téléverser.
        "photos_urls": parse_photos(annonce.images_json),
    }
