"""Router telemetry — collecte (beacon) + dashboard admin."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func
import sqlalchemy as sa
from sqlmodel import Session, select

from app.auth.deps import require_admin
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
    scope: str = Query("jour", regex="^(jour|mois|annee)$"),
):
    """Retourne les stats agrégées pour le dashboard admin.
    scope=jour  → stats du jour (temps réel events)
    scope=mois  → stats 30 jours (daily)
    scope=annee → stats 10 ans (monthly)
    """
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo("Europe/Paris")

    now_paris = datetime.now(_PARIS)
    # Minuit Paris aujourd'hui → converti en UTC naïf pour requête sur cree_le
    today_start_utc = now_paris.replace(hour=0, minute=0, second=0, microsecond=0) \
        .astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    today_paris_str = now_paris.strftime("%Y-%m-%d")

    # Offset horaire Paris (pour convertir les heures UTC → Paris dans les labels)
    paris_offset = int(now_paris.utcoffset().total_seconds() // 3600)

    if scope == "jour":
        # ── SCOPE JOUR ────────────────────────────────────────────────────
        today_stats = session.exec(
            select(
                TelemetryEvent.page,
                func.count().label("total"),
                func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
            )
            .where(TelemetryEvent.cree_le >= today_start_utc)
            .group_by(TelemetryEvent.page)
            .order_by(func.count().desc())
        ).all()

        active_today = session.exec(
            select(func.count(func.distinct(TelemetryEvent.user_id)))
            .where(TelemetryEvent.cree_le >= today_start_utc, TelemetryEvent.user_id.isnot(None))
        ).one()

        total_today = session.exec(
            select(func.count())
            .select_from(TelemetryEvent)
            .where(TelemetryEvent.cree_le >= today_start_utc)
        ).one()

        # Répartition par heure (aujourd'hui)
        hour_stats = session.exec(
            select(
                func.cast(func.strftime("%H", TelemetryEvent.cree_le), sa.Integer).label("heure"),
                func.count().label("total"),
                func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
            )
            .where(TelemetryEvent.cree_le >= today_start_utc)
            .group_by("heure")
            .order_by("heure")
        ).all()

        chart = [
            {"label": f"{(h[0] + paris_offset) % 24}h", "total": h[1], "uniques": h[2]}
            for h in hour_stats
        ]

        # Heure de pointe aujourd'hui
        hour_peak = None
        if hour_stats:
            best = max(hour_stats, key=lambda x: x[1])
            hour_peak = f"{(best[0] + paris_offset) % 24}h"

        # Moyenne vues/utilisateur
        moy_vues = round(total_today / active_today, 1) if active_today else None

        # Top users today
        user_rows = session.exec(
            select(
                TelemetryEvent.user_id,
                func.count().label("total"),
                func.count(func.distinct(TelemetryEvent.page)).label("pages"),
            )
            .where(TelemetryEvent.cree_le >= today_start_utc, TelemetryEvent.user_id.isnot(None))
            .group_by(TelemetryEvent.user_id)
            .order_by(func.count().desc())
            .limit(30)
        ).all()

        user_ids = [r[0] for r in user_rows if r[0]]
        users_map: dict[int, str] = {}
        if user_ids:
            users = session.exec(
                select(Utilisateur.id, Utilisateur.prenom, Utilisateur.nom)
                .where(Utilisateur.id.in_(user_ids))
            ).all()
            users_map = {u[0]: f"{u[1]} {u[2]}" for u in users}

        return {
            "scope": "jour",
            "kpi": {
                "utilisateurs": active_today or 0,
                "vues": total_today or 0,
                "pages": len(today_stats),
                "heure_pointe": hour_peak,
                "moy_vues_utilisateur": moy_vues,
            },
            "chart": chart,
            "chart_label": "Vues par heure",
            "top_pages": [{"page": r[0], "total": r[1], "uniques": r[2]} for r in today_stats],
            "top_users": [
                {"nom": users_map.get(r[0], "Inconnu"), "total": r[1], "pages": r[2]}
                for r in user_rows
            ],
        }

    elif scope == "mois":
        # ── SCOPE MOIS (30 jours) ────────────────────────────────────────
        thirty_days_ago = (now_paris - timedelta(days=30)).strftime("%Y-%m-%d")

        daily_rows = session.exec(
            select(TelemetryDaily)
            .where(TelemetryDaily.jour >= thirty_days_ago, TelemetryDaily.page != "__total__")
            .order_by(TelemetryDaily.jour)
        ).all()

        # Vrais uniques par jour
        daily_uniques_raw = session.exec(
            select(
                func.strftime("%Y-%m-%d", TelemetryEvent.cree_le).label("jour"),
                func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
            )
            .where(TelemetryEvent.cree_le >= thirty_days_ago, TelemetryEvent.user_id.isnot(None))
            .group_by(func.strftime("%Y-%m-%d", TelemetryEvent.cree_le))
        ).all()
        daily_uniques_map = {r[0]: r[1] for r in daily_uniques_raw}

        total_rows = session.exec(
            select(TelemetryDaily.jour, TelemetryDaily.utilisateurs_uniques)
            .where(TelemetryDaily.jour >= thirty_days_ago, TelemetryDaily.page == "__total__")
        ).all()
        for r in total_rows:
            if r[0] not in daily_uniques_map:
                daily_uniques_map[r[0]] = r[1]

        # Chart par jour
        daily_chart: dict[str, dict] = {}
        for r in daily_rows:
            if r.jour not in daily_chart:
                daily_chart[r.jour] = {"label": r.jour[5:], "total": 0, "uniques": daily_uniques_map.get(r.jour, 0)}
            daily_chart[r.jour]["total"] += r.total

        # Top pages
        top_pages: dict[str, dict] = {}
        for r in daily_rows:
            if r.page not in top_pages:
                top_pages[r.page] = {"page": r.page, "total": 0, "uniques": 0}
            top_pages[r.page]["total"] += r.total
            top_pages[r.page]["uniques"] += r.utilisateurs_uniques

        # KPI agrégés
        total_vues = sum(d["total"] for d in daily_chart.values())
        total_uniques = max(daily_uniques_map.values()) if daily_uniques_map else 0
        nb_jours = len(daily_chart) or 1
        moy_vues_jour = round(total_vues / nb_jours, 1)
        moy_utilisateurs_jour = round(sum(daily_uniques_map.values()) / nb_jours, 1) if daily_uniques_map else 0

        # Jour le plus actif (par utilisateurs uniques)
        jour_pointe = None
        if daily_uniques_map:
            best_j = max(daily_uniques_map, key=daily_uniques_map.get)  # type: ignore[arg-type]
            jour_pointe = {"jour": best_j, "uniques": daily_uniques_map[best_j]}

        # Heure de pointe (30j)
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
        if hour_stats:
            best = max(hour_stats, key=lambda x: x[1])
            peak_hour = f"{(best[0] + paris_offset) % 24}h"

        # Top users 30j
        user_rows = session.exec(
            select(
                TelemetryEvent.user_id,
                func.count().label("total"),
                func.count(func.distinct(TelemetryEvent.page)).label("pages"),
            )
            .where(TelemetryEvent.cree_le >= thirty_days_ago, TelemetryEvent.user_id.isnot(None))
            .group_by(TelemetryEvent.user_id)
            .order_by(func.count().desc())
            .limit(30)
        ).all()

        user_ids = [r[0] for r in user_rows if r[0]]
        users_map = {}
        if user_ids:
            users = session.exec(
                select(Utilisateur.id, Utilisateur.prenom, Utilisateur.nom)
                .where(Utilisateur.id.in_(user_ids))
            ).all()
            users_map = {u[0]: f"{u[1]} {u[2]}" for u in users}

        return {
            "scope": "mois",
            "kpi": {
                "vues": total_vues,
                "utilisateurs": total_uniques,
                "pages": len(top_pages),
                "heure_pointe": peak_hour,
                "moy_vues_jour": moy_vues_jour,
                "moy_utilisateurs_jour": moy_utilisateurs_jour,
                "jour_pointe": jour_pointe,
            },
            "chart": sorted(daily_chart.values(), key=lambda x: x["label"]),
            "chart_label": "Vues par jour (30j)",
            "top_pages": sorted(top_pages.values(), key=lambda x: -x["total"]),
            "top_users": [
                {"nom": users_map.get(r[0], "Inconnu"), "total": r[1], "pages": r[2]}
                for r in user_rows
            ],
        }

    else:
        # ── SCOPE ANNEE (10 ans) ─────────────────────────────────────────
        ten_years_ago = (now_paris - timedelta(days=3650)).strftime("%Y-%m")

        monthly_rows = session.exec(
            select(TelemetryMonthly)
            .where(TelemetryMonthly.mois >= ten_years_ago, TelemetryMonthly.page != "__total__")
            .order_by(TelemetryMonthly.mois)
        ).all()

        # Uniques par mois (events bruts récents + fallback __total__)
        thirty_days_ago = (now_paris - timedelta(days=30)).strftime("%Y-%m-%d")
        monthly_uniques_raw = session.exec(
            select(
                func.strftime("%Y-%m", TelemetryEvent.cree_le).label("mois"),
                func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
            )
            .where(TelemetryEvent.cree_le >= thirty_days_ago, TelemetryEvent.user_id.isnot(None))
            .group_by(func.strftime("%Y-%m", TelemetryEvent.cree_le))
        ).all()
        monthly_uniques_map = {r[0]: r[1] for r in monthly_uniques_raw}

        total_monthly_rows = session.exec(
            select(TelemetryMonthly.mois, TelemetryMonthly.utilisateurs_uniques)
            .where(TelemetryMonthly.mois >= ten_years_ago, TelemetryMonthly.page == "__total__")
        ).all()
        for r in total_monthly_rows:
            if r[0] not in monthly_uniques_map:
                monthly_uniques_map[r[0]] = r[1]

        # Chart par mois
        monthly_chart: dict[str, dict] = {}
        for r in monthly_rows:
            if r.mois not in monthly_chart:
                monthly_chart[r.mois] = {"label": r.mois, "total": 0, "uniques": monthly_uniques_map.get(r.mois, 0)}
            monthly_chart[r.mois]["total"] += r.total

        # Top pages (all time)
        top_pages_all: dict[str, dict] = {}
        for r in monthly_rows:
            if r.page not in top_pages_all:
                top_pages_all[r.page] = {"page": r.page, "total": 0, "uniques": 0}
            top_pages_all[r.page]["total"] += r.total
            top_pages_all[r.page]["uniques"] += r.utilisateurs_uniques

        total_vues = sum(d["total"] for d in monthly_chart.values())
        nb_mois_actifs = len(monthly_chart) or 1
        moy_vues_mois = round(total_vues / nb_mois_actifs, 1)

        # Records
        best_day = None
        daily_uniques_raw = session.exec(
            select(
                func.strftime("%Y-%m-%d", TelemetryEvent.cree_le).label("jour"),
                func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
            )
            .where(TelemetryEvent.user_id.isnot(None))
            .group_by(func.strftime("%Y-%m-%d", TelemetryEvent.cree_le))
        ).all()
        daily_uniques_map = {r[0]: r[1] for r in daily_uniques_raw}
        # Add fallback from daily totals
        total_daily_all = session.exec(
            select(TelemetryDaily.jour, TelemetryDaily.utilisateurs_uniques)
            .where(TelemetryDaily.page == "__total__")
        ).all()
        for r in total_daily_all:
            if r[0] not in daily_uniques_map:
                daily_uniques_map[r[0]] = r[1]

        if daily_uniques_map:
            best_jour = max(daily_uniques_map, key=daily_uniques_map.get)  # type: ignore[arg-type]
            best_day = {"jour": best_jour, "uniques": daily_uniques_map[best_jour]}

        best_month = None
        if monthly_uniques_map:
            best_mois = max(monthly_uniques_map, key=monthly_uniques_map.get)  # type: ignore[arg-type]
            best_month = {"mois": best_mois, "uniques": monthly_uniques_map[best_mois]}

        return {
            "scope": "annee",
            "kpi": {
                "vues": total_vues,
                "mois_actifs": len(monthly_chart),
                "pages": len(top_pages_all),
                "record_jour": best_day,
                "record_mois": best_month,
                "moy_vues_mois": moy_vues_mois,
            },
            "chart": sorted(monthly_chart.values(), key=lambda x: x["label"]),
            "chart_label": "Vues par mois (10 ans)",
            "top_pages": sorted(top_pages_all.values(), key=lambda x: -x["total"]),
            "top_users": [],
        }


@router.get("/users-active")
def users_active(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    """Top utilisateurs actifs sur les 30 derniers jours."""
    from zoneinfo import ZoneInfo
    thirty_days_ago = (datetime.now(ZoneInfo("Europe/Paris")) - timedelta(days=30)).strftime("%Y-%m-%d")
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
