"""Télémétrie — la COLLECTE : ce que `sendBeacon` poste depuis chaque écran.

Extraite de `routers/telemetry.py` le 28/09/2026, au fil de l'eau (#779) : le
fichier faisait 511 lignes et portait deux notions — ÉCRIRE les événements
(public, anonymes compris) et LIRE le tableau de bord (administrateur). Même
préfixe `/telemetry` : l'URL publique ne bouge pas.

## 🔴 Elle ne sait pas QUI (#1545, arbitrage du 02/10/2026)

Chaque événement portait `user_id`, collecté par défaut, avec un refus a
posteriori dans le profil. `standards/14` §4 : une mesure d'audience interne
n'échappe au consentement que si ses données sont non réidentifiantes — « une
télémétrie qui enregistre qui a vu quelle page ne remplit pas ces conditions ».
L'arbitrage n'est pas l'opt-in : c'est de ne plus savoir qui.

Cette route ne lit donc **plus le cookie de session** (#1595 : elle le décodait
elle-même, sans `actif` ni l'empreinte du mot de passe). Le refus du profil
s'applique dans le NAVIGATEUR (`front/src/lib/telemetry.ts`) : un résident qui
refuse n'envoie plus rien, et le serveur n'a pas à savoir qui a refusé pour
l'honorer.

L'heure seule est gardée, jamais la minute : un horodatage exact se recouperait
avec la dernière connexion d'un compte et rendrait une identité à l'événement.

## Le volume est borné (#1597)

Route PUBLIQUE, déclarée comme telle dans `test_autorisation.py`. Elle écrit en
base : plafond par minute ET par jour (`LIMITE_COLLECTE_ANONYME`), lot borné en
nombre, champs bornés en taille — refusés en bloc (422), pas tronqués : le
client du site n'envoie rien de tel, une charge hors norme vient d'ailleurs.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.database import get_session
from app.models.core import TelemetryEvent
from app.utils import horloge
from app.utils.limiter import LIMITE_COLLECTE_ANONYME, limiter

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
@limiter.limit(LIMITE_COLLECTE_ANONYME)
def collect(
    body: LotAudience,
    request: Request,
    session: Session = Depends(get_session),
):
    """Endpoint de collecte appelé par `sendBeacon` — anonyme, toujours."""
    heure = horloge.maintenant().replace(minute=0, second=0, microsecond=0)
    for ev in body.events:
        session.add(TelemetryEvent(page=ev.page, action=ev.action, detail=ev.detail, cree_le=heure))
    session.commit()
