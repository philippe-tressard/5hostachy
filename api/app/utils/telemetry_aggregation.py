"""Agrégation et purge de la télémétrie.

Trois niveaux de rétention :
  - Événements bruts (telemetry_event) : 30 jours
  - Agrégation journalière (telemetry_daily) : 12 mois
  - Agrégation mensuelle (telemetry_monthly) : 10 ans

Appelé quotidiennement par le scheduler ou manuellement depuis l'admin.
"""
from datetime import datetime, timedelta

from sqlalchemy import func, text
from sqlmodel import Session, select

from app.database import engine
from app.models.core import (
    TelemetryEvent, TelemetryDaily, TelemetryMonthly, HistoriqueTelemetrie,
)


def run_telemetry_aggregation(entry_id: int | None = None) -> dict:
    """Exécute l'agrégation complète et retourne un rapport.

    Si *entry_id* est fourni, met à jour l'entrée HistoriqueTelemetrie correspondante.
    """
    import time
    t0 = time.monotonic()

    rapport = {
        "jours_agreges": 0,
        "mois_agreges": 0,
        "events_purges": 0,
        "daily_purges": 0,
        "monthly_purges": 0,
        "erreurs": [],
    }

    with Session(engine) as session:
        now = datetime.utcnow()

        # ─── 1. Agrégation journalière : events → daily ─────────────────
        # Agréger les événements de la veille (et jours non encore agrégés)
        try:
            # Trouver le dernier jour agrégé
            last_daily = session.exec(
                select(TelemetryDaily.jour)
                .order_by(TelemetryDaily.jour.desc())
                .limit(1)
            ).first()

            # Commencer à partir du jour suivant le dernier agrégé, ou il y a 30 jours
            if last_daily:
                start_date = datetime.strptime(last_daily, "%Y-%m-%d") + timedelta(days=1)
            else:
                start_date = now - timedelta(days=30)

            # Ne pas agréger le jour en cours (données incomplètes)
            end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

            current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            while current < end_date:
                jour_str = current.strftime("%Y-%m-%d")
                jour_fin = current + timedelta(days=1)

                rows = session.exec(
                    select(
                        TelemetryEvent.page,
                        TelemetryEvent.action,
                        func.count().label("total"),
                        func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
                    )
                    .where(
                        TelemetryEvent.cree_le >= current,
                        TelemetryEvent.cree_le < jour_fin,
                    )
                    .group_by(TelemetryEvent.page, TelemetryEvent.action)
                ).all()

                if rows:
                    rapport["jours_agreges"] += 1
                for r in rows:
                    session.add(TelemetryDaily(
                        jour=jour_str,
                        page=r[0],
                        action=r[1],
                        total=r[2],
                        utilisateurs_uniques=r[3],
                    ))

                # Ligne __total__ : vrais uniques site-wide (COUNT DISTINCT user_id)
                if rows:
                    total_uniques = session.exec(
                        select(func.count(func.distinct(TelemetryEvent.user_id)))
                        .where(
                            TelemetryEvent.cree_le >= current,
                            TelemetryEvent.cree_le < jour_fin,
                            TelemetryEvent.user_id.isnot(None),
                        )
                    ).one() or 0
                    session.add(TelemetryDaily(
                        jour=jour_str,
                        page="__total__",
                        action="view",
                        total=sum(r[2] for r in rows),
                        utilisateurs_uniques=total_uniques,
                    ))

                current += timedelta(days=1)

            session.commit()
        except Exception as exc:
            rapport["erreurs"].append(f"agrégation daily: {exc}")
            session.rollback()

        # ─── 2. Agrégation mensuelle : daily → monthly ──────────────────
        try:
            last_monthly = session.exec(
                select(TelemetryMonthly.mois)
                .order_by(TelemetryMonthly.mois.desc())
                .limit(1)
            ).first()

            # Mois à agréger : ceux terminés et non encore agrégés
            if last_monthly:
                # Mois suivant le dernier agrégé
                y, m = map(int, last_monthly.split("-"))
                if m == 12:
                    start_month = datetime(y + 1, 1, 1)
                else:
                    start_month = datetime(y, m + 1, 1)
            else:
                start_month = now - timedelta(days=365)
                start_month = start_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Ne pas agréger le mois en cours
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            cursor = start_month
            while cursor < current_month_start:
                mois_str = cursor.strftime("%Y-%m")

                rows = session.exec(
                    select(
                        TelemetryDaily.page,
                        TelemetryDaily.action,
                        func.sum(TelemetryDaily.total).label("total"),
                        func.sum(TelemetryDaily.utilisateurs_uniques).label("uniques"),
                    )
                    .where(
                        TelemetryDaily.jour.startswith(mois_str),
                        TelemetryDaily.page != "__total__",
                    )
                    .group_by(TelemetryDaily.page, TelemetryDaily.action)
                ).all()

                for r in rows:
                    if r[2]:  # Ne pas insérer si aucune donnée
                        session.add(TelemetryMonthly(
                            mois=mois_str,
                            page=r[0],
                            action=r[1],
                            total=r[2],
                            utilisateurs_uniques=r[3],
                        ))

                # Ligne __total__ mensuelle : somme des __total__ daily du mois
                total_row = session.exec(
                    select(
                        func.sum(TelemetryDaily.total).label("total"),
                        func.sum(TelemetryDaily.utilisateurs_uniques).label("uniques"),
                    )
                    .where(
                        TelemetryDaily.jour.startswith(mois_str),
                        TelemetryDaily.page == "__total__",
                    )
                ).first()
                if total_row and total_row[0]:
                    session.add(TelemetryMonthly(
                        mois=mois_str,
                        page="__total__",
                        action="view",
                        total=total_row[0],
                        # Approximation : somme des uniques quotidiens (même user sur 2 jours = compté 2×)
                        # Acceptable pour les tendances mensuelles longue durée.
                        utilisateurs_uniques=total_row[1] or 0,
                    ))

                if any(r[2] for r in rows):
                    rapport["mois_agreges"] += 1

                # Avancer au mois suivant
                if cursor.month == 12:
                    cursor = cursor.replace(year=cursor.year + 1, month=1)
                else:
                    cursor = cursor.replace(month=cursor.month + 1)

            session.commit()
        except Exception as exc:
            rapport["erreurs"].append(f"agrégation monthly: {exc}")
            session.rollback()

        # ─── 3. Purge : events > 30 jours ───────────────────────────────
        try:
            cutoff = now - timedelta(days=30)
            with engine.connect() as conn:
                result = conn.execute(
                    text("DELETE FROM telemetry_event WHERE cree_le < :cutoff"),
                    {"cutoff": cutoff.isoformat()},
                )
                conn.commit()
                rapport["events_purges"] = result.rowcount
        except Exception as exc:
            rapport["erreurs"].append(f"purge events: {exc}")

        # ─── 4. Purge : daily > 12 mois ─────────────────────────────────
        try:
            cutoff_daily = (now - timedelta(days=365)).strftime("%Y-%m-%d")
            with engine.connect() as conn:
                result = conn.execute(
                    text("DELETE FROM telemetry_daily WHERE jour < :cutoff"),
                    {"cutoff": cutoff_daily},
                )
                conn.commit()
                rapport["daily_purges"] = result.rowcount
        except Exception as exc:
            rapport["erreurs"].append(f"purge daily: {exc}")

        # ─── 5. Purge : monthly > 10 ans ────────────────────────────────
        try:
            cutoff_monthly = (now - timedelta(days=3650)).strftime("%Y-%m")
            with engine.connect() as conn:
                result = conn.execute(
                    text("DELETE FROM telemetry_monthly WHERE mois < :cutoff"),
                    {"cutoff": cutoff_monthly},
                )
                conn.commit()
                rapport["monthly_purges"] = result.rowcount
        except Exception as exc:
            rapport["erreurs"].append(f"purge monthly: {exc}")

    # ─── Mise à jour de l'historique ──────────────────────────────────
    duree = round(time.monotonic() - t0, 2)
    if entry_id is not None:
        with Session(engine) as session:
            entry = session.get(HistoriqueTelemetrie, entry_id)
            if entry:
                entry.jours_agreges = rapport["jours_agreges"]
                entry.mois_agreges = rapport["mois_agreges"]
                entry.events_purges = rapport["events_purges"]
                entry.daily_purges = rapport["daily_purges"]
                entry.monthly_purges = rapport["monthly_purges"]
                entry.duree_secondes = duree
                entry.terminee_le = datetime.utcnow()
                if rapport["erreurs"]:
                    entry.statut = "erreur"
                    entry.erreur = "; ".join(rapport["erreurs"])
                else:
                    entry.statut = "succes"
                session.add(entry)
                session.commit()

    rapport["duree_secondes"] = duree
    return rapport


def run_telemetry_aggregation_cron() -> dict:
    """Wrapper appelé par le scheduler cron — crée automatiquement une entrée historique."""
    with Session(engine) as session:
        entry = HistoriqueTelemetrie(declenchee_par="cron")
        session.add(entry)
        session.commit()
        session.refresh(entry)
        entry_id = entry.id
    return run_telemetry_aggregation(entry_id)
