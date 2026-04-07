"""Envoi d'emails via fastapi-mail + templates Jinja2 stockés en base."""
from datetime import datetime
from typing import Any

from jinja2 import Environment, BaseLoader
from sqlmodel import Session, select

from app.config import get_settings
from app.models.core import ConfigSite, ModeleEmail, Utilisateur

settings = get_settings()

_SMTP_KEYS = {'smtp_enabled', 'smtp_server', 'smtp_port', 'smtp_from', 'smtp_from_name', 'smtp_username', 'smtp_password', 'smtp_starttls', 'smtp_ssl_tls'}


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
):
    """
    Récupère le ModèleEmail par code, rend sujet + corps, envoie si MAIL_ENABLED.
    Fail graceful : en cas d'erreur, log sans bloquer l'événement déclencheur.
    
    Note: Si appelé depuis une BackgroundTask, la session passée peut être fermée.
    Une nouvelle session est créée automatiquement si nécessaire.
    """
    from app.database import SessionLocal
    
    # Créer une nouvelle session si elle n'existe pas (pour les background tasks)
    if session is None:
        session = SessionLocal()
        close_session = True
    else:
        close_session = False
    
    try:
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

        # Variables communes
        base_ctx = {
            "annee": datetime.utcnow().year,
            "app": {"url": "https://localhost"},
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
            msg_kwargs = dict(
                subject=_render(template.sujet, ctx),
                recipients=[to],
                body=_render(template.corps_html, ctx),
                subtype="html",
            )
            if cc:
                msg_kwargs["cc"] = cc
            if attachments:
                msg_kwargs["attachments"] = attachments
            msg = MessageSchema(**msg_kwargs)
            await fm.send_message(msg)
        except Exception as exc:
            # Log l'erreur sans bloquer
            import logging
            logging.getLogger("email").error("Erreur envoi email [%s] → %s : %s", code, to, exc)
    finally:
        if close_session:
            session.close()
