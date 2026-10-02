"""Router telemetry — le tableau de bord de l'administrateur.

La COLLECTE (`POST /telemetry/collect`, publique) vit dans `telemetry_collecte.py`
depuis le 28/09/2026 (#779) : écrire et lire sont deux notions, et ce fichier
dépassait 500 lignes.

🔴 DES VUES, PLUS DES PERSONNES (#1545, 02/10/2026). L'événement ne porte plus
d'identifiant : les indicateurs « utilisateurs actifs », « utilisateurs
uniques », la colonne « Utilisateurs » des pages, le tableau « Utilisateurs les
plus actifs » et la route `GET /telemetry/users-active` sont retirés — ils
n'avaient plus de matière, et les garder aurait affiché des zéros comme une
mesure. Le jour le plus actif et les records se jugent désormais aux vues.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
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
from app.utils.telemetrie_calculs import _cumul_par_page, record

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


# ── Dashboard admin ───────────────────────────────────────────────────────────


def _vues_par_heure(session: Session, depuis: datetime):
    """(heure UTC, vues) depuis `depuis`, triés par heure."""
    return session.exec(
        select(
            func.cast(func.strftime("%H", TelemetryEvent.cree_le), sa.Integer).label("heure"),
            func.count().label("total"),
        )
        .where(TelemetryEvent.cree_le >= depuis)
        .group_by("heure")
        .order_by("heure")
    ).all()


def _heure_de_pointe(heures, decalage: int) -> str | None:
    """L'heure (Paris) qui a compté le plus de vues, ou `None` s'il n'y en a aucune."""
    if not heures:
        return None
    meilleure = max(heures, key=lambda x: x[1])
    return f"{(meilleure[0] + decalage) % 24}h"


@router.get("/dashboard")
def dashboard(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
    scope: str = Query("jour", pattern="^(jour|mois|annee)$"),
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
    today_start_utc = (
        now_paris.replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(ZoneInfo("UTC"))
        .replace(tzinfo=None)
    )

    # Offset horaire Paris (pour convertir les heures UTC → Paris dans les labels)
    paris_offset = int(now_paris.utcoffset().total_seconds() // 3600)

    if scope == "jour":
        # ── SCOPE JOUR ────────────────────────────────────────────────────
        today_stats = session.exec(
            select(TelemetryEvent.page, func.count().label("total"))
            .where(TelemetryEvent.cree_le >= today_start_utc)
            .group_by(TelemetryEvent.page)
            .order_by(func.count().desc())
        ).all()

        hour_stats = _vues_par_heure(session, today_start_utc)

        # Convertir en heure Paris et trier correctement
        chart = sorted(
            ({"paris_h": (h[0] + paris_offset) % 24, "total": h[1]} for h in hour_stats),
            key=lambda x: x["paris_h"],
        )

        return {
            "scope": "jour",
            "kpi": {
                "vues": sum(r[1] for r in today_stats),
                "pages": len(today_stats),
                "heure_pointe": _heure_de_pointe(hour_stats, paris_offset),
            },
            "chart": [{"label": f"{c['paris_h']}h", "total": c["total"]} for c in chart],
            "chart_label": "Vues par heure",
            "top_pages": [{"page": r[0], "total": r[1]} for r in today_stats],
        }

    elif scope == "mois":
        # ── SCOPE MOIS (30 jours) ────────────────────────────────────────
        thirty_days_ago = (now_paris - timedelta(days=30)).strftime("%Y-%m-%d")

        daily_rows = session.exec(
            select(TelemetryDaily)
            .where(TelemetryDaily.jour >= thirty_days_ago, TelemetryDaily.page != "__total__")
            .order_by(TelemetryDaily.jour)
        ).all()

        vues_par_jour: dict[str, int] = {}
        for r in daily_rows:
            vues_par_jour[r.jour] = vues_par_jour.get(r.jour, 0) + r.total

        top_pages = _cumul_par_page(daily_rows)
        total_vues = sum(vues_par_jour.values())
        nb_jours = len(vues_par_jour) or 1

        return {
            "scope": "mois",
            "kpi": {
                "vues": total_vues,
                "pages": len(top_pages),
                "heure_pointe": _heure_de_pointe(
                    _vues_par_heure(session, now_paris.replace(tzinfo=None) - timedelta(days=30)),
                    paris_offset,
                ),
                "moy_vues_jour": round(total_vues / nb_jours, 1),
                "jour_pointe": record(vues_par_jour, "jour"),
            },
            "chart": [
                {"label": jour[5:], "total": vues} for jour, vues in sorted(vues_par_jour.items())
            ],
            "chart_label": "Vues par jour (30j)",
            "top_pages": sorted(top_pages.values(), key=lambda x: -x["total"]),
        }

    else:
        # ── SCOPE ANNEE (10 ans) ─────────────────────────────────────────
        ten_years_ago = (now_paris - timedelta(days=3650)).strftime("%Y-%m")

        monthly_rows = session.exec(
            select(TelemetryMonthly)
            .where(TelemetryMonthly.mois >= ten_years_ago, TelemetryMonthly.page != "__total__")
            .order_by(TelemetryMonthly.mois)
        ).all()

        vues_par_mois: dict[str, int] = {}
        for r in monthly_rows:
            vues_par_mois[r.mois] = vues_par_mois.get(r.mois, 0) + r.total

        #  Le record du jour se lit dans les agrégats journaliers, gardés 12 mois :
        #  la ligne `__total__` porte toutes les vues du jour.
        vues_par_jour = dict(
            session.exec(
                select(TelemetryDaily.jour, TelemetryDaily.total).where(
                    TelemetryDaily.page == "__total__"
                )
            ).all()
        )

        top_pages_all = _cumul_par_page(monthly_rows)
        total_vues = sum(vues_par_mois.values())
        nb_mois_actifs = len(vues_par_mois) or 1

        return {
            "scope": "annee",
            "kpi": {
                "vues": total_vues,
                "mois_actifs": len(vues_par_mois),
                "pages": len(top_pages_all),
                "record_jour": record(vues_par_jour, "jour"),
                "record_mois": record(vues_par_mois, "mois"),
                "moy_vues_mois": round(total_vues / nb_mois_actifs, 1),
            },
            "chart": [
                {"label": mois, "total": vues} for mois, vues in sorted(vues_par_mois.items())
            ],
            "chart_label": "Vues par mois (10 ans)",
            "top_pages": sorted(top_pages_all.values(), key=lambda x: -x["total"]),
        }
