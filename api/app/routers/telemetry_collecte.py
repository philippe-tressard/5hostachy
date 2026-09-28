"""Télémétrie — la COLLECTE : ce que `sendBeacon` poste depuis chaque écran.

Extraite de `routers/telemetry.py` le 28/09/2026, au fil de l'eau (#779) : le
fichier faisait 511 lignes et portait deux notions — ÉCRIRE les événements
(public, anonymes compris) et LIRE le tableau de bord (administrateur). Même
préfixe `/telemetry` : l'URL publique ne bouge pas.

⚠️ Route PUBLIQUE, déclarée comme telle dans `test_autorisation.py` : rate-limitée,
plafonnée à 50 événements, champs tronqués, opt-out RGPD honoré.
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlmodel import Session

from app.database import get_session
from app.models.core import TelemetryEvent, Utilisateur
from app.utils import horloge
from app.utils.limiter import LIMITE_JOURNAL, limiter

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


class TelemetryBatch(BaseModel):
    events: list[dict]  # [{page, action?, detail?}, ...]


@router.post("/collect", status_code=204)
@limiter.limit(LIMITE_JOURNAL)
def collect(
    body: TelemetryBatch,
    request: Request,
    session: Session = Depends(get_session),
):
    """Endpoint de collecte appelé par sendBeacon.
    Authentification via cookie (credentials: include) — silencieux si non connecté."""
    user_id: int | None = None
    try:
        from app.auth.jwt import decode_token

        token = request.cookies.get("access_token")
        if token:
            payload = decode_token(token)
            if payload and payload.get("type") == "access":
                user_id = int(payload["sub"])
                # RGPD opt-out : l'utilisateur a désactivé la télémétrie
                u = session.get(Utilisateur, user_id)
                if u and u.opt_out_telemetrie:
                    return
    except Exception:
        pass  # Visiteur non connecté — on enregistre quand même avec user_id=None

    now = horloge.maintenant()
    for ev in body.events[:50]:  # Max 50 événements par batch (sécurité)
        page = str(ev.get("page", ""))[:200]
        action = str(ev.get("action", "view"))[:50]
        detail = ev.get("detail")
        if detail is not None:
            detail = str(detail)[:500]
        if not page:
            continue
        session.add(
            TelemetryEvent(
                user_id=user_id,
                page=page,
                action=action,
                detail=detail,
                cree_le=now,
            )
        )
    session.commit()
