"""Envoi d'emails via fastapi-mail + templates Jinja2 stockés en base."""
import json
import logging
from datetime import datetime
from typing import Any

from jinja2 import Environment, BaseLoader
from sqlmodel import Session, select

from app.config import get_settings
from app.models.core import ConfigSite, ModeleEmail, Utilisateur

settings = get_settings()

_SMTP_KEYS = {'smtp_enabled', 'smtp_server', 'smtp_port', 'smtp_from', 'smtp_from_name', 'smtp_username', 'smtp_password', 'smtp_starttls', 'smtp_ssl_tls'}

# Mapping code email → clé préférence utilisateur (catégorie_mail)
# Les codes absents (system, account) sont toujours envoyés.
_EMAIL_PREF_MAP: dict[str, str] = {
    "ticket_cree_cs": "ticket_mail",
    "ticket_bug_admin": "ticket_mail",
    "ticket_statut_change": "ticket_mail",
    "ticket_urgence_bailleur": "ticket_mail",
    "ticket_syndic": "ticket_mail",
    "calendrier_evenement_cree": "actu_mail",
    "digest_quotidien": "actu_mail",
    "digest_hebdomadaire": "actu_mail",
    "document_publie": "doc_mail",
}

logger = logging.getLogger("email")


def get_site_manager_notification_email(session: Session) -> tuple[str, dict[str, str]]:
    """Retourne l'email de notification du gestionnaire du site et la config lue."""
    rows = session.exec(
        select(ConfigSite).where(
            ConfigSite.cle.in_(("site_email", "site_nom", "site_url", "site_manager_user_id"))
        )
    ).all()
    config = {row.cle: row.valeur for row in rows}

    site_email = (config.get("site_email") or "").strip()
    site_manager_email = ""
    site_manager_user_id = (config.get("site_manager_user_id") or "").strip()
    if site_manager_user_id.isdigit():
        manager_user = session.get(Utilisateur, int(site_manager_user_id))
        if manager_user and manager_user.email:
            site_manager_email = manager_user.email.strip()

    return site_manager_email or site_email, config


def _get_smtp_config(session: Session) -> dict:
    rows = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(_SMTP_KEYS))).all()
    return {r.cle: r.valeur for r in rows}


def _render(template_str: str, context: dict) -> str:
    env = Environment(loader=BaseLoader())
    tmpl = env.from_string(template_str)
    return tmpl.render(**context)


async def send_email(
    code: str,
    to: str,
    context: dict[str, Any],
    session: Session | None = None,
    *,
    cc: list[str] | None = None,
    attachments: list[str] | None = None,
    destinataire_id: int | None = None,
):
    """
    Récupère le ModèleEmail par code, rend sujet + corps, envoie si MAIL_ENABLED.
    Fail graceful : en cas d'erreur, log sans bloquer l'événement déclencheur.
    
    Si *destinataire_id* est fourni et que le code email est lié à une
    catégorie de préférence, l'email n'est envoyé que si l'utilisateur
    a activé la préférence correspondante.
    """
    from app.database import SessionLocal
    
    # Créer une nouvelle session si elle n'existe pas (pour les background tasks)
    if session is None:
        session = SessionLocal()
        close_session = True
    else:
        close_session = False
    
    try:
        # ── Vérification préférence utilisateur ──────────────────────────
        pref_key = _EMAIL_PREF_MAP.get(code)
        if pref_key and destinataire_id:
            user = session.get(Utilisateur, destinataire_id)
            if user:
                try:
                    prefs = json.loads(user.preferences_notifications or "{}")
                except (json.JSONDecodeError, TypeError):
                    prefs = {}
                if not prefs.get(pref_key, True):
                    logger.debug("Email [%s] non envoyé → préférence %s=false pour user %s", code, pref_key, destinataire_id)
                    return

        smtp_cfg = _get_smtp_config(session)
        if smtp_cfg.get('smtp_enabled') is not None:
            if smtp_cfg['smtp_enabled'] != '1':
                return
        elif not settings.mail_enabled:
            return

        template: ModeleEmail | None = session.exec(
            select(ModeleEmail).where(ModeleEmail.code == code)
        ).first()
        if not template or not template.actif:
            return

        # ── Footer email (similaire au footer WhatsApp) ──────────────────
        email_footer_row = session.get(ConfigSite, "email_footer")
        email_footer = (email_footer_row.valeur if email_footer_row else "").strip()

        # Variables communes
        site_nom_row = session.get(ConfigSite, "site_nom")
        site_url_row = session.get(ConfigSite, "site_url")
        base_ctx = {
            "annee": datetime.utcnow().year,
            "app": {"url": (site_url_row.valeur if site_url_row else "https://localhost")},
            "residence": {"nom": (site_nom_row.valeur if site_nom_row else "Ma Résidence")},
        }
        ctx = {**base_ctx, **context}

        try:
            from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

            _srv = smtp_cfg.get('smtp_server') or settings.mail_server
            _port = int(smtp_cfg.get('smtp_port') or settings.mail_port)
            _from = smtp_cfg.get('smtp_from') or settings.mail_from
            _from_name = smtp_cfg.get('smtp_from_name') or settings.mail_from_name
            _username = smtp_cfg.get('smtp_username') or settings.mail_username
            _password = smtp_cfg.get('smtp_password') or settings.mail_password
            _starttls = (smtp_cfg['smtp_starttls'] == '1') if 'smtp_starttls' in smtp_cfg else settings.mail_starttls
            _ssl_tls = (smtp_cfg['smtp_ssl_tls'] == '1') if 'smtp_ssl_tls' in smtp_cfg else settings.mail_ssl_tls
            cfg = ConnectionConfig(
                MAIL_USERNAME=_username,
                MAIL_PASSWORD=_password,
                MAIL_FROM=_from,
                MAIL_FROM_NAME=_from_name,
                MAIL_PORT=_port,
                MAIL_SERVER=_srv,
                MAIL_STARTTLS=_starttls,
                MAIL_SSL_TLS=_ssl_tls,
                USE_CREDENTIALS=bool(_username),
            )
            fm = FastMail(cfg)
            rendered_body = _render(template.corps_html, ctx)
            if email_footer:
                rendered_body += f'<p style="color:#888;font-size:12px;margin-top:24px;border-top:1px solid #ddd;padding-top:12px">{email_footer}</p>'
            msg_kwargs = dict(
                subject=_render(template.sujet, ctx),
                recipients=[to],
                body=rendered_body,
                subtype="html",
            )
            if cc:
                msg_kwargs["cc"] = cc
            if attachments:
                msg_kwargs["attachments"] = attachments
            msg = MessageSchema(**msg_kwargs)
            await fm.send_message(msg)
        except Exception as exc:
            logger.error("Erreur envoi email [%s] → %s : %s", code, to, exc)
    finally:
        if close_session:
            session.close()
