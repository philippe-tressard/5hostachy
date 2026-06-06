"""Vérification quotidienne de santé du système — WhatsApp, sauvegardes, disque."""
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone

import httpx
from sqlmodel import Session, select

from app.database import SessionLocal
from app.models.core import ConfigSite, HistoriqueSauvegarde, StatutSauvegarde, WhatsAppLog

logger = logging.getLogger(__name__)

_WA_KEYS = {"whatsapp_enabled", "whatsapp_api_url", "whatsapp_api_key"}


def _check_whatsapp(session: Session) -> list[str]:
    """Retourne une liste de problèmes WhatsApp détectés."""
    issues = []
    cfg = {r.cle: r.valeur for r in session.exec(
        select(ConfigSite).where(ConfigSite.cle.in_(_WA_KEYS))
    ).all()}

    if cfg.get("whatsapp_enabled") != "1":
        return []

    api_url = cfg.get("whatsapp_api_url", "").strip()
    api_key = cfg.get("whatsapp_api_key", "").strip()
    if not api_url:
        return []

    # Vérifier le statut du bridge
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{api_url.rstrip('/')}/status", headers={"x-api-key": api_key})
            state = resp.json().get("state", "unknown")
        if state != "open":
            issues.append(f"Bridge WhatsApp déconnecté (état : {state}). Reconnexion requise via Admin → WhatsApp → Statut.")
    except Exception as exc:
        issues.append(f"Bridge WhatsApp injoignable : {exc}")
        return issues

    # Vérifier les logs des dernières 24h : >= 3 échecs consécutifs
    # (on ignore les anciens échecs antérieurs à une reconnexion)
    depuis = datetime.utcnow() - timedelta(hours=24)
    logs = session.exec(
        select(WhatsAppLog)
        .where(WhatsAppLog.envoye_le >= depuis)
        .order_by(WhatsAppLog.envoye_le.desc())
        .limit(5)
    ).all()
    if len(logs) >= 3 and all(l.statut == "échec" for l in logs[:3]):
        last_err = logs[0].erreur or "erreur inconnue"
        issues.append(
            f"3 derniers envois WhatsApp en échec consécutif (dernières 24h). Dernière erreur : {last_err}"
        )

    return issues


def _check_backups(session: Session) -> list[str]:
    """Retourne une liste de problèmes de sauvegarde détectés."""
    issues = []
    last_ok = session.exec(
        select(HistoriqueSauvegarde)
        .where(HistoriqueSauvegarde.statut == StatutSauvegarde.reussie)
        .order_by(HistoriqueSauvegarde.terminee_le.desc())
    ).first()

    if not last_ok or not last_ok.terminee_le:
        issues.append("Aucune sauvegarde réussie trouvée dans l'historique.")
        return issues

    age = datetime.utcnow() - last_ok.terminee_le
    if age > timedelta(hours=25):
        heures = int(age.total_seconds() / 3600)
        issues.append(
            f"Dernière sauvegarde réussie il y a {heures}h (> 25h). "
            f"Vérifier Admin → Sauvegardes."
        )

    # Dernière sauvegarde en échec ?
    last_any = session.exec(
        select(HistoriqueSauvegarde).order_by(HistoriqueSauvegarde.terminee_le.desc())
    ).first()
    if last_any and last_any.statut == StatutSauvegarde.echouee:
        issues.append(
            f"La dernière sauvegarde a échoué : {last_any.message_erreur or 'erreur inconnue'}."
        )

    return issues


def _check_disk() -> list[str]:
    """Retourne une alerte si l'espace disque est faible."""
    issues = []
    try:
        usage = shutil.disk_usage("/")
        pct_free = (usage.free / usage.total) * 100
        if pct_free < 15:
            free_gb = usage.free / (1024 ** 3)
            issues.append(
                f"Espace disque faible : {pct_free:.1f}% libre ({free_gb:.1f} Go). "
                f"Vérifier et nettoyer si nécessaire."
            )
    except Exception as exc:
        logger.warning("Impossible de vérifier l'espace disque : %s", exc)
    return issues


def _send_alert(to: str, issues: list[str], session: Session) -> None:
    """Envoie l'email d'alerte système."""
    import smtplib
    from email.mime.text import MIMEText
    from zoneinfo import ZoneInfo

    smtp_cfg = {r.cle: r.valeur for r in session.exec(select(ConfigSite)).all()}

    server = smtp_cfg.get("smtp_server", "").strip()
    port = int(smtp_cfg.get("smtp_port") or 587)
    username = smtp_cfg.get("smtp_username", "").strip()
    password = smtp_cfg.get("smtp_password", "").strip()
    from_addr = smtp_cfg.get("smtp_from", username).strip()
    site_nom = smtp_cfg.get("site_nom", "5Hostachy")
    site_url = (smtp_cfg.get("site_url") or "https://5hostachy.fr").rstrip("/")

    if not server or not username:
        logger.warning("Alerte santé non envoyée : SMTP non configuré.")
        return

    now_paris = datetime.now(ZoneInfo("Europe/Paris")).strftime("%-d %B %Y à %H:%M")
    lignes = "\n".join(f"  • {i}" for i in issues)
    body = (
        f"Bonjour,\n\n"
        f"Le contrôle quotidien de {site_nom} a détecté {len(issues)} problème(s) "
        f"le {now_paris} :\n\n"
        f"{lignes}\n\n"
        f"Accédez à l'interface d'administration :\n{site_url}/admin\n\n"
        f"— Système de surveillance {site_nom}"
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"[{site_nom}] ⚠️ Alerte système — {len(issues)} problème(s) détecté(s)"
    msg["From"] = f"{site_nom} <{from_addr}>"
    msg["To"] = to

    try:
        use_tls = smtp_cfg.get("smtp_starttls", "1") == "1"
        with smtplib.SMTP(server, port) as s:
            if use_tls:
                s.starttls()
            s.login(username, password)
            s.sendmail(from_addr, [to], msg.as_string())
        logger.info("Alerte santé envoyée à %s (%d problème(s)).", to, len(issues))
    except Exception as exc:
        logger.error("Échec envoi alerte santé : %s", exc)


def run_health_check() -> None:
    """Job quotidien : vérifie WhatsApp, sauvegardes, disque — alerte si problème."""
    from app.utils.email import get_site_manager_notification_email

    session = SessionLocal()
    try:
        issues: list[str] = []
        issues += _check_whatsapp(session)
        issues += _check_backups(session)
        issues += _check_disk()

        if not issues:
            logger.info("Contrôle santé quotidien : tout est OK.")
            return

        logger.warning("Contrôle santé : %d problème(s) détecté(s).", len(issues))
        for i in issues:
            logger.warning("  • %s", i)

        to, _ = get_site_manager_notification_email(session)
        if to:
            _send_alert(to, issues, session)
        else:
            logger.warning("Alerte santé non envoyée : aucun email admin configuré.")
    except Exception as exc:
        logger.error("Erreur contrôle santé quotidien : %s", exc)
    finally:
        session.close()
