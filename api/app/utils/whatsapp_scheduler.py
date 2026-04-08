"""Planificateur de messages WhatsApp récurrents.

Logique : chaque jour à 18h, vérifie si demain est le Nème samedi du mois
correspondant à une règle cron_rule, et envoie le message.
"""
import calendar
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.database import engine
from app.models.core import WhatsAppScheduled, WhatsAppLog, ConfigSite

logger = logging.getLogger(__name__)


def _nth_weekday(year: int, month: int, weekday: int, n: int):
    """Retourne la date du Nème jour de la semaine (0=lun..5=sam) du mois."""
    cal = calendar.monthcalendar(year, month)
    count = 0
    for week in cal:
        if week[weekday] != 0:
            count += 1
            if count == n:
                return week[weekday]
    return None


def _is_friday_before_nth_saturday(dt: datetime, n: int) -> bool:
    """Vérifie si dt est le vendredi 18h avant le Nème samedi du mois."""
    if dt.weekday() != 4:  # 4 = vendredi
        return False
    saturday = dt.date() + timedelta(days=1)
    day = _nth_weekday(saturday.year, saturday.month, calendar.SATURDAY, n)
    return day is not None and saturday.day == day


def check_and_send():
    """Vérifie les messages planifiés et envoie ceux qui correspondent à aujourd'hui."""
    from app.utils.whatsapp import envoyer_whatsapp_raw

    now = datetime.now(ZoneInfo("Europe/Paris"))
    logger.info("WhatsApp scheduler check at %s", now.strftime("%Y-%m-%d %H:%M"))

    with Session(engine) as session:
        schedules = session.exec(
            select(WhatsAppScheduled).where(WhatsAppScheduled.enabled == True)
        ).all()

        if not schedules:
            return

        # Charger la config WhatsApp
        rows = session.exec(select(ConfigSite)).all()
        config = {r.cle: r.valeur for r in rows}

        if config.get('whatsapp_enabled') != '1':
            logger.info("WhatsApp désactivé, pas d'envoi planifié.")
            return

        for sched in schedules:
            should_send = False
            if sched.cron_rule == "3eme_samedi":
                should_send = _is_friday_before_nth_saturday(now, 3)
            elif sched.cron_rule == "4eme_samedi":
                should_send = _is_friday_before_nth_saturday(now, 4)

            if not should_send:
                continue

            # Vérifier qu'on n'a pas déjà envoyé aujourd'hui pour ce message
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            existing = session.exec(
                select(WhatsAppLog).where(
                    WhatsAppLog.scheduled_id == sched.id,
                    WhatsAppLog.envoye_le >= today_start,
                    WhatsAppLog.statut == "envoyé",
                )
            ).first()
            if existing:
                logger.info("Message '%s' déjà envoyé aujourd'hui.", sched.label)
                continue

            log = WhatsAppLog(
                scheduled_id=sched.id,
                label=sched.label,
                message=sched.message,
            )
            try:
                envoyer_whatsapp_raw(sched.message, config)
                log.statut = "envoyé"
                logger.info("Message planifié '%s' envoyé.", sched.label)
            except Exception as exc:
                log.statut = "échec"
                log.erreur = str(exc)
                logger.warning("Échec envoi planifié '%s': %s", sched.label, exc)

            session.add(log)
            session.commit()

            # Garder seulement les 6 derniers logs
            _prune_logs(session)


def _prune_logs(session: Session):
    """Conserve uniquement les 6 derniers messages envoyés."""
    all_logs = session.exec(
        select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc())
    ).all()
    if len(all_logs) > 6:
        for old in all_logs[6:]:
            session.delete(old)
        session.commit()
