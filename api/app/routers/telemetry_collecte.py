"""Télémétrie — la COLLECTE : ce que `sendBeacon` poste depuis chaque écran.

Extraite de `routers/telemetry.py` le 28/09/2026, au fil de l'eau (#779) : le
fichier faisait 511 lignes et portait deux notions — ÉCRIRE les événements
(public, anonymes compris) et LIRE le tableau de bord (administrateur). Même
préfixe `/telemetry` : l'URL publique ne bouge pas.

## Elle sait QUI — rétablie le 02/10/2026

La v2.92.0 (#1545) avait retiré `user_id` : le tableau de bord avait perdu ses
statistiques par utilisateur (actifs, palmarès…), sans l'accord de
l'utilisateur du produit. Elles sont rétablies (migration 0247), la politique
de confidentialité dit de nouveau « rattachées à votre compte », et le refus du
profil est honoré ICI comme dans le navigateur.

## La session se lit par `auth/deps.py`, jamais ici (#1595)

Avant #1595, cette route décodait le cookie elle-même — sans `actif` ni
l'empreinte du mot de passe : une session invalidée restait reconnue. Elle
prend `utilisateur_ou_anonyme`, la même chaîne que toute route authentifiée,
qui rend `None` au lieu d'un 401 pour un visiteur.

## Le volume est borné (#1597)

Route PUBLIQUE, déclarée comme telle dans `test_autorisation.py`. Elle écrit en
base : plafond par minute ET par jour (`LIMITE_COLLECTE_AUDIENCE`), lot borné en
nombre, champs bornés en taille — refusés en bloc (422), pas tronqués : le
client du site n'envoie rien de tel, une charge hors norme vient d'ailleurs.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import utilisateur_ou_anonyme
from app.database import get_session
from app.models.core import TelemetryEvent, Utilisateur
from app.utils import horloge
from app.utils.limiter import LIMITE_COLLECTE_AUDIENCE, limiter

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

#: Le client vide sa file toutes les 30 secondes, et dès qu'elle atteint ce
#: nombre (`front/src/lib/telemetry.ts`, `EVENEMENTS_PAR_LOT`) : un lot plus
#: gros ne vient pas de lui. ⚠️ Les deux valeurs se tiennent à la main — le
#: front et l'API ne partagent aucun fichier (contextes de build séparés).
EVENEMENTS_PAR_LOT = 20


class EvenementAudience(BaseModel):
    page: str = Field(min_length=1, max_length=200)  # chemin, sans requête
    action: str = Field(default="view", max_length=20)
    detail: str | None = Field(default=None, max_length=100)


class LotAudience(BaseModel):
    events: list[EvenementAudience] = Field(max_length=EVENEMENTS_PAR_LOT)


@router.post("/collect", status_code=204)
@limiter.limit(LIMITE_COLLECTE_AUDIENCE)
def collect(
    body: LotAudience,
    request: Request,
    session: Session = Depends(get_session),
    user: Utilisateur | None = Depends(utilisateur_ou_anonyme),
):
    """Endpoint de collecte appelé par `sendBeacon` — rattaché au compte s'il y en a un."""
    if user and user.opt_out_telemetrie:
        return  # RGPD art. 21 : le refus du profil vaut aussi côté serveur
    user_id = user.id if user else None
    now = horloge.maintenant()
    for ev in body.events:
        session.add(
            TelemetryEvent(
                user_id=user_id, page=ev.page, action=ev.action, detail=ev.detail, cree_le=now
            )
        )
    session.commit()
