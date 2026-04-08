"""Router telemetry — collecte (beacon) + dashboard admin."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import (
    TelemetryEvent,
    TelemetryDaily,
    TelemetryMonthly,
    Utilisateur,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


# ── Collecte (fire-and-forget depuis sendBeacon) ─────────────────────────────

class TelemetryBatch(BaseModel):
    events: list[dict]  # [{page, action?, detail?}, ...]


@router.post("/collect", status_code=204)
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
    except Exception:
        pass  # Visiteur non connecté — on enregistre quand même avec user_id=None

    now = datetime.utcnow()
    for ev in body.events[:50]:  # Max 50 événements par batch (sécurité)
        page = str(ev.get("page", ""))[:200]
        action = str(ev.get("action", "view"))[:50]
        detail = ev.get("detail")
        if detail is not None:
            detail = str(detail)[:500]
        if not page:
            continue
        session.add(TelemetryEvent(
            user_id=user_id,
            page=page,
            action=action,
            detail=detail,
            cree_le=now,
        ))
    session.commit()


# ── Dashboard admin ───────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Retourne les stats agrégées pour le dashboard admin."""
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    month_start = now.strftime("%Y-%m-01")
    thirty_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    # --- Stats temps réel (aujourd'hui) depuis telemetry_event ---
    today_stats = session.exec(
        select(
            TelemetryEvent.page,
            func.count().label("total"),
            func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
        )
        .where(TelemetryEvent.cree_le >= today)
        .group_by(TelemetryEvent.page)
        .order_by(func.count().desc())
    ).all()

    # --- 30 derniers jours (depuis telemetry_daily) ---
    daily_rows = session.exec(
        select(TelemetryDaily)
        .where(TelemetryDaily.jour >= thirty_days_ago)
        .order_by(TelemetryDaily.jour)
    ).all()

    # Agrégation par jour pour le graphe
    daily_chart: dict[str, dict] = {}
    for r in daily_rows:
        if r.jour not in daily_chart:
            daily_chart[r.jour] = {"jour": r.jour, "total": 0, "uniques": 0}
        daily_chart[r.jour]["total"] += r.total
        daily_chart[r.jour]["uniques"] += r.uniques

    # Top pages sur 30 jours
    top_pages_30d: dict[str, dict] = {}
    for r in daily_rows:
        if r.page not in top_pages_30d:
            top_pages_30d[r.page] = {"page": r.page, "total": 0, "uniques": 0}
        top_pages_30d[r.page]["total"] += r.total
        top_pages_30d[r.page]["uniques"] += r.uniques

    # --- 12 derniers mois (depuis telemetry_monthly) ---
    twelve_months_ago = (now - timedelta(days=365)).strftime("%Y-%m")
    monthly_rows = session.exec(
        select(TelemetryMonthly)
        .where(TelemetryMonthly.mois >= twelve_months_ago)
        .order_by(TelemetryMonthly.mois)
    ).all()

    monthly_chart: dict[str, dict] = {}
    for r in monthly_rows:
        if r.mois not in monthly_chart:
            monthly_chart[r.mois] = {"mois": r.mois, "total": 0, "uniques": 0}
        monthly_chart[r.mois]["total"] += r.total
        monthly_chart[r.mois]["uniques"] += r.uniques

    # --- Utilisateurs actifs aujourd'hui ---
    active_today = session.exec(
        select(func.count(func.distinct(TelemetryEvent.user_id)))
        .where(TelemetryEvent.cree_le >= today, TelemetryEvent.user_id.isnot(None))
    ).one()

    # --- Total vues aujourd'hui ---
    total_today = session.exec(
        select(func.count())
        .select_from(TelemetryEvent)
        .where(TelemetryEvent.cree_le >= today)
    ).one()

    return {
        "today": {
            "active_users": active_today or 0,
            "total_views": total_today or 0,
            "pages": [{"page": r[0], "total": r[1], "uniques": r[2]} for r in today_stats],
        },
        "daily": sorted(daily_chart.values(), key=lambda x: x["jour"]),
        "top_pages_30d": sorted(top_pages_30d.values(), key=lambda x: -x["total"]),
        "monthly": sorted(monthly_chart.values(), key=lambda x: x["mois"]),
    }


@router.get("/users-active")
def users_active(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Top utilisateurs actifs sur les 30 derniers jours."""
    thirty_days_ago = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    rows = session.exec(
        select(
            TelemetryEvent.user_id,
            func.count().label("total"),
            func.count(func.distinct(TelemetryEvent.page)).label("pages"),
        )
        .where(
            TelemetryEvent.cree_le >= thirty_days_ago,
            TelemetryEvent.user_id.isnot(None),
        )
        .group_by(TelemetryEvent.user_id)
        .order_by(func.count().desc())
        .limit(30)
    ).all()

    # Enrichir avec les noms
    user_ids = [r[0] for r in rows if r[0]]
    users_map: dict[int, str] = {}
    if user_ids:
        users = session.exec(
            select(Utilisateur.id, Utilisateur.prenom, Utilisateur.nom)
            .where(Utilisateur.id.in_(user_ids))
        ).all()
        users_map = {u[0]: f"{u[1]} {u[2]}" for u in users}

    return [
        {
            "user_id": r[0],
            "nom": users_map.get(r[0], "Inconnu"),
            "total": r[1],
            "pages": r[2],
        }
        for r in rows
    ]
