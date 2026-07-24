"""Planificateur de messages WhatsApp récurrents.

Logique : de 18h00 à 21h45 (toutes les 15 min), vérifie si demain est le Nème
samedi du mois correspondant à une règle cron_rule, et envoie le message.

Fenêtre de rattrapage (depuis l'incident du 24/07/2026) : le job ne tentait
auparavant l'envoi qu'une seule fois, à 18h00 pile — une panne ponctuelle du
bridge WhatsApp à cette seconde précise faisait perdre le message du mois.
La déduplication (basée uniquement sur un log au statut "envoyé") rend les
tentatives répétées sûres : aucun risque de doublon. Si la fenêtre se ferme
sans envoi réussi, une alerte email est déclenchée.
"""
import calendar
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session, select

from app.database import engine
from app.models.core import WhatsAppScheduled, WhatsAppLog, ConfigSite

logger = logging.getLogger(__name__)

# Dernière tentative de la fenêtre de rattrapage — doit correspondre au dernier
# déclenchement du cron APScheduler (hour='18-21', minute='*/15') dans main.py.
CATCHUP_END_HOUR = 21
CATCHUP_END_MINUTE = 45


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
    is_last_attempt = (now.hour, now.minute) == (CATCHUP_END_HOUR, CATCHUP_END_MINUTE)
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

            # Tentatives déjà faites aujourd'hui pour ce message (tout statut)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_logs = session.exec(
                select(WhatsAppLog)
                .where(
                    WhatsAppLog.scheduled_id == sched.id,
                    WhatsAppLog.envoye_le >= today_start,
                )
                .order_by(WhatsAppLog.envoye_le.desc())
            ).all()

            if any(l.statut == "envoyé" for l in today_logs):
                logger.info("Message '%s' déjà envoyé aujourd'hui.", sched.label)
                continue

            footer = (config.get('whatsapp_footer') or '').strip() or "— Conseil Syndical 5Hostachy"
            message_complet = f"{sched.message}\n\n{footer}"

            # Réutilise le log d'échec du jour au lieu d'en empiler un nouveau à
            # chaque créneau de 15 min — sinon _prune_logs (qui ne garde que les
            # 6 derniers logs, tous messages confondus) purgerait tout
            # l'historique récent en moins de 2h de tentatives.
            log = today_logs[0] if today_logs else WhatsAppLog(
                scheduled_id=sched.id,
                label=sched.label,
            )
            log.message = message_complet
            log.envoye_le = datetime.utcnow()

            try:
                envoyer_whatsapp_raw(message_complet, config)
                log.statut = "envoyé"
                log.erreur = None
                logger.info("Message planifié '%s' envoyé.", sched.label)
            except Exception as exc:
                log.statut = "échec"
                log.erreur = str(exc)
                logger.warning("Échec envoi planifié '%s': %s", sched.label, exc)

            session.add(log)
            session.commit()

            if log.statut == "échec" and is_last_attempt:
                _alert_missed(session, sched, log.erreur)

            # Garder seulement les 6 derniers logs
            _prune_logs(session)


def _alert_missed(session: Session, sched: WhatsAppScheduled, erreur: str | None) -> None:
    """Alerte email si la fenêtre de rattrapage se ferme sans envoi réussi."""
    from app.utils.email import get_site_manager_notification_email
    from app.utils.health_monitor import _send_alert

    to, _ = get_site_manager_notification_email(session)
    if not to:
        logger.warning(
            "Message planifié '%s' définitivement manqué (fenêtre de rattrapage épuisée) "
            "— pas d'email admin configuré pour alerter.",
            sched.label,
        )
        return
    issue = (
        f"Message WhatsApp planifié « {sched.label} » non envoyé malgré la fenêtre "
        f"de rattrapage (18h00 → {CATCHUP_END_HOUR:02d}h{CATCHUP_END_MINUTE:02d}).\n"
        f"    Dernière erreur : {erreur or 'inconnue'}"
    )
    _send_alert(to, [issue], session)


def _prune_logs(session: Session):
    """Conserve uniquement les 6 derniers messages envoyés."""
    all_logs = session.exec(
        select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc())
    ).all()
    if len(all_logs) > 6:
        for old in all_logs[6:]:
            session.delete(old)
        session.commit()
