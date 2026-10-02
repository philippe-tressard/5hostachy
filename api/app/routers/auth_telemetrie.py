"""Le refus de la mesure d'audience — une préférence du compte.

## Pourquoi ce module (#835, 08/09/2026)

Extrait d'`auth.py` quand le garde-fou de modularité a refusé de le laisser
grossir. Le refus disait vrai : ces routes ne parlent pas d'authentification.

⚠️ Le préfixe reste `/auth` : la route est publiée sous `/auth/me/…` depuis
toujours, et un client l'appelle. Déplacer le code ne déplace pas l'adresse.

## 🔴 Plus d'export ni d'effacement (#1545, 02/10/2026)

Ce module servait aussi `GET` et `DELETE /auth/me/telemetrie` — accès,
portabilité et effacement de « sa » télémétrie. Depuis que l'événement ne porte
plus d'identifiant, il n'y a plus de télémétrie À SOI : rien à rendre, rien à
effacer. Les garder aurait rendu une liste vide en prétendant répondre à un droit.

Le REFUS reste, et c'est voulu : une collecte anonyme peut garder un refus
volontaire. Il s'applique dans le navigateur (`front/src/lib/telemetry.ts`) —
qui refuse n'envoie plus rien — et le compte le retient d'un appareil à l'autre.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Utilisateur
from app.utils.limiter import LIMITE_PREFERENCE, limiter

router = APIRouter(prefix="/auth", tags=["auth"])


class OptOutTelemetrieBody(BaseModel):
    opt_out_telemetrie: bool


@router.patch("/me/opt-out-telemetrie", status_code=204)
@limiter.limit(LIMITE_PREFERENCE)
def toggle_opt_out_telemetrie(
    request: Request,
    body: OptOutTelemetrieBody,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Refuser — ou accepter à nouveau — la mesure d'audience (RGPD art. 21)."""
    user.opt_out_telemetrie = body.opt_out_telemetrie
    session.add(user)
    session.commit()
