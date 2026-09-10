"""Agrégation et purge de la télémétrie.

Trois niveaux de rétention :
  - Événements bruts (telemetry_event) : 30 jours
  - Agrégation journalière (telemetry_daily) : 12 mois
  - Agrégation mensuelle (telemetry_monthly) : 10 ans

Appelé quotidiennement par le scheduler ou manuellement depuis l'admin.

NOTE : Les événements (cree_le) sont stockés en UTC.
Les bornes jour/mois utilisent le fuseau Europe/Paris pour que le
découpage corresponde aux journées réelles des utilisateurs.
"""
from datetime import datetime, timedelta
import logging
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, text
from sqlmodel import Session, select

from app.database import engine
from app.models.core import (
    TelemetryEvent, TelemetryDaily, TelemetryMonthly, HistoriqueTelemetrie,
)
from app.utils.noeud import noeud_courant

logger = logging.getLogger(__name__)

_PARIS = ZoneInfo("Europe/Paris")


def _paris_now() -> datetime:
    """Heure actuelle en Europe/Paris (aware)."""
    return datetime.now(_PARIS)


def _paris_midnight(dt_paris: datetime) -> datetime:
    """Retourne minuit Paris du jour donné, converti en UTC naïf
    (pour comparaison avec les cree_le stockés en UTC naïf)."""
    midnight = dt_paris.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


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
        now_utc = datetime.utcnow()
        now_paris = _paris_now()

        # ─── 1. Agrégation journalière : events → daily ─────────────────
        # Agréger les événements de la veille (et jours non encore agrégés)
        # Les bornes utilisent le fuseau Paris pour correspondre aux jours réels.
        try:
            # Trouver le dernier jour agrégé
            last_daily = session.exec(
                select(TelemetryDaily.jour)
                .order_by(TelemetryDaily.jour.desc())
                .limit(1)
            ).first()

            # Commencer à partir du jour suivant le dernier agrégé, ou il y a 30 jours
            if last_daily:
                start_paris = datetime.strptime(last_daily, "%Y-%m-%d").replace(tzinfo=_PARIS) + timedelta(days=1)
            else:
                start_paris = now_paris - timedelta(days=30)

            # Ne pas agréger le jour en cours (données incomplètes)
            # end = minuit Paris aujourd'hui (= début du jour courant)
            end_utc = _paris_midnight(now_paris)
            current_paris = start_paris.replace(hour=0, minute=0, second=0, microsecond=0)

            while True:
                current_utc = _paris_midnight(current_paris)
                if current_utc >= end_utc:
                    break
                jour_str = current_paris.strftime("%Y-%m-%d")
                next_paris = current_paris + timedelta(days=1)
                jour_fin_utc = _paris_midnight(next_paris)

                rows = session.exec(
                    select(
                        TelemetryEvent.page,
                        TelemetryEvent.action,
                        func.count().label("total"),
                        func.count(func.distinct(TelemetryEvent.user_id)).label("uniques"),
                    )
                    .where(
                        TelemetryEvent.cree_le >= current_utc,
                        TelemetryEvent.cree_le < jour_fin_utc,
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
                            TelemetryEvent.cree_le >= current_utc,
                            TelemetryEvent.cree_le < jour_fin_utc,
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

                current_paris = next_paris

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
                    start_month = datetime(y + 1, 1, 1, tzinfo=_PARIS)
                else:
                    start_month = datetime(y, m + 1, 1, tzinfo=_PARIS)
            else:
                start_month = (now_paris - timedelta(days=365)).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0)

            # Ne pas agréger le mois en cours
            current_month_start = now_paris.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

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
            cutoff = now_utc - timedelta(days=30)
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
            cutoff_daily = (now_paris - timedelta(days=365)).strftime("%Y-%m-%d")
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
            cutoff_monthly = (now_paris - timedelta(days=3650)).strftime("%Y-%m")
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


def rattrapage_necessaire(
    derniere_reussite: Optional[datetime],
    maintenant: datetime,
    periode_h: int = 24,
) -> bool:
    """L'agrégation a-t-elle MANQUÉ un passage ?

    ## L'incident (10/09/2026, #876)

    Le déploiement de 01:58 a redémarré la pile ; le planificateur est reparti à
    **02:00:13**, soit treize secondes après le créneau du job. APScheduler tient
    ses jobs en mémoire : au redémarrage, il ne sait pas qu'un passage a été
    manqué, et calcule le suivant à partir de l'instant d'ajout. L'agrégation du
    10 septembre n'a pas eu lieu, et la suivante était prévue le 11.

    🔴 **Ce n'était pas un hasard.** `auto-deploy.sh` tourne toutes les cinq
    minutes, et `bascule.sh` redémarre la pile **à 02:00 précises** en cron root
    — la même minute que ce job. La collision est structurelle ; cette nuit-là,
    c'est la mise en production qui a gagné la course.

    ## Pourquoi cette fonction plutôt que `misfire_grace_time`

    La grâce d'APScheduler couvre un retard **du processus vivant**, pas un
    arrêt : sans jobstore persistant, il n'y a rien à rattraper au démarrage.
    C'est donc le FAIT qu'on interroge — *quand la dernière agrégation a-t-elle
    réussi ?* — et non l'horaire. La même réponse couvre alors toutes les causes
    d'arrêt : mise en production, bascule, coupure de courant, panne.

    ⚠️ **Aucune trace du tout ⇒ on rattrape.** Base neuve ou tâche jamais passée,
    les deux méritent une première exécution — et elle est inoffensive.

    ⚠️ La comparaison porte sur la dernière **réussite**, pas sur la dernière
    tentative : une ligne en `erreur` prouve que la tâche a tourné, pas qu'elle a
    agrégé quoi que ce soit.
    """
    if derniere_reussite is None:
        return True
    return (maintenant - derniere_reussite) > timedelta(hours=periode_h)


def derniere_agregation_reussie(session) -> Optional[datetime]:
    """L'horodatage de la dernière agrégation qui a abouti, ou `None`."""
    ligne = session.exec(
        select(HistoriqueTelemetrie)
        .where(HistoriqueTelemetrie.statut == "succes")
        .order_by(HistoriqueTelemetrie.cree_le.desc())
        .limit(1)
    ).first()
    return ligne.cree_le if ligne else None


def rattraper_si_manquee() -> Optional[dict]:
    """Lance l'agrégation si son dernier passage réussi remonte à plus de 24 h.

    Appelée **au démarrage**, une fois. Rend `None` quand il n'y a rien à
    rattraper — et c'est le cas nominal, qu'on journalise quand même : un chemin
    muet est un chemin qu'on croit vivant (le contrat de battement, `standards/07`).
    """
    with Session(engine) as session:
        derniere = derniere_agregation_reussie(session)
    if not rattrapage_necessaire(derniere, datetime.utcnow()):
        logger.info(
            "Agrégation télémétrie : rien à rattraper (dernière réussite %s).",
            derniere.isoformat() if derniere else "aucune",
        )
        return None
    logger.warning(
        "Agrégation télémétrie : passage MANQUÉ (dernière réussite %s) — rattrapage.",
        derniere.isoformat() if derniere else "aucune",
    )
    return run_telemetry_aggregation_cron()


def run_telemetry_aggregation_cron() -> dict:
    """Wrapper appelé par le scheduler cron — crée automatiquement une entrée historique."""
    with Session(engine) as session:
        entry = HistoriqueTelemetrie(declenchee_par="cron", noeud=noeud_courant())
        session.add(entry)
        session.commit()
        session.refresh(entry)
        entry_id = entry.id
    return run_telemetry_aggregation(entry_id)
