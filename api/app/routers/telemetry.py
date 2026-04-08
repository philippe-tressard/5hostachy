"""Router telemetry — collecte (beacon) + dashboard admin."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, text
import sqlalchemy as sa
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import (
    TelemetryEvent,
    TelemetryDaily,
    TelemetryMonthly,
    Utilisateur,
)
from app.utils.limiter import limiter

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


# ── Collecte (fire-and-forget depuis sendBeacon) ─────────────────────────────

class TelemetryBatch(BaseModel):
    events: list[dict]  # [{page, action?, detail?}, ...]


@router.post("/collect", status_code=204)
@limiter.limit("60/minute")
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

    # --- Heure moyenne de plus forte / plus faible audience (30 derniers jours) ---
    # Les heures sont stockées en UTC — conversion vers Europe/Paris
    from zoneinfo import ZoneInfo
    paris_offset = int(now.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Europe/Paris")).utcoffset().total_seconds() // 3600)

    hour_stats = session.exec(
        select(
            func.cast(func.strftime("%H", TelemetryEvent.cree_le), sa.Integer).label("heure"),
            func.count().label("total"),
        )
        .where(TelemetryEvent.cree_le >= thirty_days_ago)
        .group_by("heure")
        .order_by("heure")
    ).all()

    peak_hour = None
    low_hour = None
    if hour_stats:
        sorted_hours = sorted(hour_stats, key=lambda x: x[1])
        low_hour = {"heure": (sorted_hours[0][0] + paris_offset) % 24, "vues": sorted_hours[0][1]}
        peak_hour = {"heure": (sorted_hours[-1][0] + paris_offset) % 24, "vues": sorted_hours[-1][1]}

    # --- Jour du mois de plus forte audience (moyenne sur données daily) ---
    day_of_month_stats = session.exec(
        select(
            func.cast(func.substr(TelemetryDaily.jour, 9, 2), sa.Integer).label("jour_mois"),
            func.avg(TelemetryDaily.total).label("moyenne"),
        )
        .group_by("jour_mois")
        .order_by(func.avg(TelemetryDaily.total).desc())
        .limit(1)
    ).first()

    peak_day_of_month = None
    if day_of_month_stats:
        peak_day_of_month = {
            "jour": day_of_month_stats[0],
            "moyenne_vues": round(float(day_of_month_stats[1]), 1),
        }

    # --- Records d'utilisateurs uniques (10 ans glissant) ---
    # Meilleur jour (depuis telemetry_daily — toutes les données disponibles)
    best_day = session.exec(
        select(
            TelemetryDaily.jour,
            func.sum(TelemetryDaily.utilisateurs_uniques).label("uniques"),
        )
        .group_by(TelemetryDaily.jour)
        .order_by(func.sum(TelemetryDaily.utilisateurs_uniques).desc())
        .limit(1)
    ).first()

    # Meilleur mois (depuis telemetry_monthly — 10 ans)
    best_month = session.exec(
        select(
            TelemetryMonthly.mois,
            func.sum(TelemetryMonthly.utilisateurs_uniques).label("uniques"),
        )
        .group_by(TelemetryMonthly.mois)
        .order_by(func.sum(TelemetryMonthly.utilisateurs_uniques).desc())
        .limit(1)
    ).first()

    records = {
        "best_day": {"jour": best_day[0], "uniques": best_day[1]} if best_day else None,
        "best_month": {"mois": best_month[0], "uniques": best_month[1]} if best_month else None,
    }

    return {
        "today": {
            "active_users": active_today or 0,
            "total_views": total_today or 0,
            "pages": [{"page": r[0], "total": r[1], "uniques": r[2]} for r in today_stats],
        },
        "daily": sorted(daily_chart.values(), key=lambda x: x["jour"]),
        "top_pages_30d": sorted(top_pages_30d.values(), key=lambda x: -x["total"]),
        "monthly": sorted(monthly_chart.values(), key=lambda x: x["mois"]),
        "peak_hour": peak_hour,
        "low_hour": low_hour,
        "peak_day_of_month": peak_day_of_month,
        "records": records,
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
