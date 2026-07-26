"""Vérification quotidienne de santé du système — WhatsApp, sauvegardes, disque."""
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone

import httpx
from sqlmodel import Session, select

from app.database import SessionLocal
from app.utils.dates_fr import datetime_longue
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
        from zoneinfo import ZoneInfo
        extrait = "\n".join(
            f"    [{l.envoye_le.replace(tzinfo=ZoneInfo('UTC')).astimezone(ZoneInfo('Europe/Paris')).strftime('%d/%m %H:%M')}] "
            f"« {l.label[:40]} » → {l.erreur or 'erreur inconnue'}"
            for l in logs[:3]
        )
        issues.append(
            f"3 derniers envois WhatsApp en échec consécutif (dernières 24h) :\n{extrait}"
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


def _check_db_integrity() -> list[str]:
    """Vérifie l'intégrité de la base SQLite (PRAGMA quick_check).

    Exécuté DANS le process API (même connexion que l'app) → aucun accès
    multi-process. Détecte tôt une corruption (ex. telemetry_event 17/06/2026,
    découverte seulement par l'échec du job d'agrégation) au lieu d'attendre
    un signalement utilisateur.
    """
    from sqlalchemy import text
    from app.database import engine

    issues: list[str] = []
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA quick_check")).first()
        verdict = res[0] if res else "(aucun résultat)"
        if verdict != "ok":
            issues.append(
                f"Intégrité base CORROMPUE (PRAGMA quick_check : « {verdict} »). "
                f"Récupération requise (.recover) — voir CLAUDE.md → corruption DB."
            )
    except Exception as exc:
        # quick_check lui-même peut lever si la corruption est sévère
        issues.append(
            f"Intégrité base : quick_check a échoué ({exc}). "
            f"Base probablement corrompue — récupération requise (.recover)."
        )
    return issues


def _send_alert(to: str, issues: list[str], session: Session) -> None:
    """Envoie l'email d'alerte système avec le gabarit HTML du site."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from zoneinfo import ZoneInfo
    from app.utils.email import _wrap_email

    smtp_cfg = {r.cle: r.valeur for r in session.exec(select(ConfigSite)).all()}

    server = smtp_cfg.get("smtp_server", "").strip()
    port = int(smtp_cfg.get("smtp_port") or 587)
    username = smtp_cfg.get("smtp_username", "").strip()
    password = smtp_cfg.get("smtp_password", "").strip()
    from_addr = smtp_cfg.get("smtp_from", username).strip()
    from_name = smtp_cfg.get("smtp_from_name", "").strip()
    site_nom = smtp_cfg.get("site_nom", "5Hostachy")
    site_url = (smtp_cfg.get("site_url") or "https://5hostachy.fr").rstrip("/")
    footer = smtp_cfg.get("email_footer", "")

    if not server or not username:
        logger.warning("Alerte santé non envoyée : SMTP non configuré.")
        return

    now_paris = datetime_longue(datetime.now(ZoneInfo("Europe/Paris")))
    annee = datetime.now().year

    # ── Construction du corps HTML ────────────────────────────────────────
    blocs_html = []
    for issue in issues:
        lignes = issue.split("\n")
        titre = lignes[0]
        details = lignes[1:] if len(lignes) > 1 else []
        detail_html = ""
        if details:
            rows = "".join(
                f'<tr><td style="padding:4px 0;font-size:13px;color:#4A5568;font-family:monospace">{l.strip()}</td></tr>'
                for l in details
            )
            detail_html = (
                f'<table role="presentation" cellpadding="0" cellspacing="0" '
                f'style="width:100%;background:#F8F9FA;border-left:3px solid #E53E3E;'
                f'border-radius:4px;padding:10px 14px;margin-top:8px">'
                f'{rows}</table>'
            )
        blocs_html.append(
            f'<tr><td style="padding:10px 0 6px">'
            f'<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%">'
            f'<tr><td style="vertical-align:top;width:24px;padding-top:2px">'
            f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#E53E3E;margin-top:4px"></span>'
            f'</td>'
            f'<td style="vertical-align:top;font-size:15px;color:#1A1A2E;line-height:1.5">{titre}</td>'
            f'</tr>'
            f'{"<tr><td></td><td>" + detail_html + "</td></tr>" if detail_html else ""}'
            f'</table>'
            f'</td></tr>'
        )

    issues_html = "\n".join(blocs_html)

    body_html = f"""
<p style="margin:0 0 8px;font-size:15px;color:#4A5568">Bonjour,</p>
<p style="margin:0 0 24px;font-size:15px;color:#4A5568">
  Le contrôle quotidien du <strong>{now_paris}</strong> a détecté
  <strong style="color:#E53E3E">{len(issues)} problème(s)</strong> :
</p>

<table role="presentation" cellpadding="0" cellspacing="0"
  style="width:100%;border:1px solid #FED7D7;border-radius:8px;
         background:#FFF5F5;padding:16px 20px;margin-bottom:24px">
  {issues_html}
</table>

<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%">
  <tr><td align="center">
    <a href="{site_url}/admin"
       style="display:inline-block;background:#1E3A5F;color:#FFFFFF;
              font-size:14px;font-weight:600;padding:12px 28px;
              border-radius:6px;text-decoration:none;letter-spacing:0.3px">
      Accéder à l'administration
    </a>
  </td></tr>
</table>
"""

    full_html = _wrap_email(body_html, site_nom, site_url, footer, annee)

    # ── Envoi ─────────────────────────────────────────────────────────────
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{site_nom}] ⚠️ Alerte système — {len(issues)} problème(s) détecté(s)"
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["To"] = to
    msg.attach(MIMEText(full_html, "html", "utf-8"))

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
        issues += _check_db_integrity()
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
