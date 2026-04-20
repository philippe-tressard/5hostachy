"""Envoi d'emails via fastapi-mail + templates Jinja2 stockés en base."""
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any

from jinja2.sandbox import SandboxedEnvironment
from jinja2 import BaseLoader
from sqlmodel import Session, select

from app.config import get_settings
from app.models.core import ConfigSite, HistoriqueEmail, ModeleEmail, Utilisateur

settings = get_settings()

_SMTP_KEYS = {'smtp_enabled', 'smtp_server', 'smtp_port', 'smtp_from', 'smtp_from_name', 'smtp_username', 'smtp_password', 'smtp_starttls', 'smtp_ssl_tls'}

# Mapping code email → clé préférence utilisateur (catégorie_mail)
# Les codes absents (system, account) sont toujours envoyés.
_EMAIL_PREF_MAP: dict[str, str] = {
    "ticket_cree_cs": "ticket_mail",
    "ticket_bug_admin": "ticket_mail",
    "ticket_statut_change": "ticket_mail",
    "ticket_nouveau_message": "ticket_mail",
    "ticket_urgence_bailleur": "ticket_mail",
    "ticket_syndic": "ticket_mail",
    "publication_syndic": "actu_mail",
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


def _log_email(session: Session, code: str, to: str, statut: str, *, sujet: str = "", erreur: str | None = None) -> None:
    """Enregistre une entrée dans historique_email (fail-safe)."""
    try:
        entry = HistoriqueEmail(code=code, destinataire=to, sujet=sujet[:200], statut=statut, erreur=erreur)
        session.add(entry)
        session.commit()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass


def _render(template_str: str, context: dict) -> str:
    env = SandboxedEnvironment(loader=BaseLoader())
    tmpl = env.from_string(template_str)
    return tmpl.render(**context)


# ── Logo SVG inline (favicon du site) — base64 pour compatibilité email ──
_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="48" height="48">'
    '<rect width="64" height="64" rx="14" fill="#1E3A5F"/>'
    '<g fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M18 54V18a4 4 0 0 1 4-4h20a4 4 0 0 1 4 4v36Z"/>'
    '<path d="M18 34h-6a4 4 0 0 0-4 4v16h10"/>'
    '<path d="M46 30h6a4 4 0 0 1 4 4v20H46"/>'
    '<path d="M25 22h14"/><path d="M25 30h14"/><path d="M25 38h14"/><path d="M25 46h14"/>'
    '</g>'
    '<path d="M48 50c0 4.4-3.6 8-8 8h14a8 8 0 0 0-6-8Z" fill="#C9983A" opacity=".95"/>'
    '</svg>'
)


import re as _re


def _linkify_urls(text: str) -> str:
    """Transforme les URLs brutes en liens cliquables dans le footer."""
    return _re.sub(
        r'(https?://\S+|(?<!\w)([a-zA-Z0-9-]+\.)+[a-z]{2,}(?:/\S*)?)',
        lambda m: f'<a href="{m.group(0) if m.group(0).startswith("http") else "https://" + m.group(0)}" '
                  f'style="color:#1E3A5F;text-decoration:underline">{m.group(0)}</a>',
        text,
    )


def _wrap_email(body_html: str, site_nom: str, site_url: str, footer: str, annee: int) -> str:
    """Encapsule le contenu HTML dans un gabarit email aux couleurs du site."""
    safe_footer = ""
    if footer:
        linked_footer = _linkify_urls(footer)
        safe_footer = (
            f'<tr><td style="background-color:#FAFAF7;padding:20px 32px 24px;text-align:center">'
            f'<p style="margin:0;font-size:13px;color:#5A6070">{linked_footer}</p>'
            f'</td></tr>'
        )
    return f'''<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{site_nom}</title></head>
<body style="margin:0;padding:0;background-color:#F2EFE9;font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Roboto,'Helvetica Neue',Arial,sans-serif;color:#1A1A2E;-webkit-text-size-adjust:100%">

<!-- Wrapper -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F2EFE9;padding:24px 0">
<tr><td align="center">

<!-- Container -->
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(30,58,95,0.12)">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#1E3A5F 0%,#16304F 100%);padding:28px 32px;text-align:center">
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto"><tr>
      <td style="vertical-align:middle;padding-right:14px">{_LOGO_SVG}</td>
      <td style="vertical-align:middle;text-align:left">
        <div style="font-family:Georgia,'Palatino Linotype','Book Antiqua',Palatino,serif;font-size:22px;font-weight:700;color:#FFFFFF;letter-spacing:0.3px">{site_nom}</div>
        <div style="font-size:12px;color:#C9983A;letter-spacing:1.5px;text-transform:uppercase;margin-top:2px;font-weight:600">Espace numérique de résidence</div>
      </td>
    </tr></table>
  </td></tr>

  <!-- Accent bar -->
  <tr><td style="height:4px;background:linear-gradient(90deg,#C9983A 0%,#1E3A5F 50%,#3D6B4F 100%)"></td></tr>

  <!-- Body -->
  <tr><td style="background-color:#FFFFFF;padding:32px 32px 24px;font-size:15px;line-height:1.65;color:#1A1A2E">
    {body_html}
  </td></tr>

  <!-- Notification preferences -->
  <tr><td style="background-color:#FFFFFF;padding:0 32px 20px;text-align:center">
    <p style="margin:0;font-size:12px;color:#8A8FA0">Pour g\u00e9rer vos pr\u00e9f\u00e9rences de notification, rendez-vous dans votre <a href="{site_url.rstrip('/')}/profil" style="color:#1E3A5F;text-decoration:underline">profil</a>.</p>
  </td></tr>

  <!-- Footer -->
  {safe_footer}

</table>
<!-- /Container -->

</td></tr>
</table>
<!-- /Wrapper -->
</body>
</html>'''


def _fix_image_orientations(paths: list[str]) -> list[str]:
    """Applique la rotation EXIF sur les images JPEG et retourne les chemins corrigés."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return paths

    fixed: list[str] = []
    for path in paths:
        ext = os.path.splitext(path)[1].lower()
        if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
            fixed.append(path)
            continue
        try:
            with Image.open(path) as img:
                corrected = ImageOps.exif_transpose(img)
                if corrected is img:
                    # Pas de correction nécessaire
                    fixed.append(path)
                    continue
                tmp = tempfile.NamedTemporaryFile(
                    suffix=ext, prefix="exif_", dir=os.path.dirname(path), delete=False,
                )
                corrected.save(tmp.name, quality=92)
                tmp.close()
                fixed.append(tmp.name)
        except Exception:
            fixed.append(path)
    return fixed


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

    Les images jointes sont automatiquement corrigées (orientation EXIF) avant envoi.
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
                    _log_email(session, code, to, "ignore", erreur=f"préférence {pref_key}=false")
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
            _log_email(session, code, to, "ignore", erreur="template inactive ou inexistante")
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
            site_nom = site_nom_row.valeur if site_nom_row else "Ma Résidence"
            site_url = site_url_row.valeur if site_url_row else "https://localhost"
            full_html = _wrap_email(
                rendered_body,
                site_nom=site_nom,
                site_url=site_url,
                footer=email_footer,
                annee=ctx["annee"],
            )
            rendered_subject = _render(template.sujet, ctx)
            msg_kwargs = dict(
                subject=rendered_subject,
                recipients=[to],
                body=full_html,
                subtype="html",
            )
            if cc:
                msg_kwargs["cc"] = cc
            fixed_attachments: list[str] = []
            if attachments:
                fixed_attachments = _fix_image_orientations(attachments)
                msg_kwargs["attachments"] = fixed_attachments
            msg = MessageSchema(**msg_kwargs)
            await fm.send_message(msg)
            _log_email(session, code, to, "succes", sujet=rendered_subject)
        except Exception as exc:
            logger.error("Erreur envoi email [%s] → %s : %s", code, to, exc)
            _log_email(session, code, to, "erreur", erreur=str(exc)[:500])
    finally:
        # Nettoyer les fichiers temporaires EXIF
        if attachments:
            for fp in fixed_attachments:
                if fp not in attachments:
                    try:
                        os.unlink(fp)
                    except OSError:
                        pass
        if close_session:
            session.close()


def _check_pref(code: str, user_id: int | None, session: Session) -> bool:
    """Retourne False si l'utilisateur a désactivé la préférence pour ce code email."""
    pref_key = _EMAIL_PREF_MAP.get(code)
    if not pref_key or not user_id:
        return True
    user = session.get(Utilisateur, user_id)
    if not user:
        return True
    try:
        prefs = json.loads(user.preferences_notifications or "{}")
    except (json.JSONDecodeError, TypeError):
        prefs = {}
    return prefs.get(pref_key, True)


async def send_email_group(
    code: str,
    to_recipients: list[tuple[int | None, str]],
    context: dict[str, Any],
    session: Session | None = None,
    *,
    cc_recipients: list[tuple[int | None, str]] | None = None,
    attachments: list[str] | None = None,
):
    """
    Envoie UN seul email groupé à plusieurs destinataires (to + cc optionnel).

    - to_recipients  : liste (user_id | None, email) — destinataires principaux (se voient entre eux)
    - cc_recipients  : liste (user_id | None, email) — destinataires en copie (ex: auteur du ticket)
    - Les préférences de chaque utilisateur sont vérifiées individuellement en amont.
    - Un seul enregistrement dans historique_email liste tous les destinataires.
    - Les pièces jointes (photos) sont transmises si fournies.
    """
    from app.database import SessionLocal

    if session is None:
        session = SessionLocal()
        close_session = True
    else:
        close_session = False

    fixed_attachments: list[str] = []
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

        # Filtrage des préférences individuelles
        filtered_to = [
            (uid, email) for uid, email in to_recipients
            if _check_pref(code, uid, session)
        ]
        filtered_cc = [
            (uid, email) for uid, email in (cc_recipients or [])
            if _check_pref(code, uid, session)
        ]

        if not filtered_to and not filtered_cc:
            return

        to_emails = [email for _, email in filtered_to]
        cc_emails = [email for _, email in filtered_cc]
        all_emails_str = ", ".join(to_emails + cc_emails)

        # Contexte
        email_footer_row = session.get(ConfigSite, "email_footer")
        email_footer = (email_footer_row.valeur if email_footer_row else "").strip()
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
            site_nom = site_nom_row.valeur if site_nom_row else "Ma Résidence"
            site_url = site_url_row.valeur if site_url_row else "https://localhost"
            rendered_body = _render(template.corps_html, ctx)
            full_html = _wrap_email(
                rendered_body,
                site_nom=site_nom,
                site_url=site_url,
                footer=email_footer,
                annee=ctx["annee"],
            )
            rendered_subject = _render(template.sujet, ctx)
            msg_kwargs: dict[str, Any] = dict(
                subject=rendered_subject,
                recipients=to_emails if to_emails else cc_emails,
                body=full_html,
                subtype="html",
            )
            # CC : uniquement si to non vide (sinon tous en recipients)
            if to_emails and cc_emails:
                msg_kwargs["cc"] = cc_emails
            # Pièces jointes (photos) — correction orientation EXIF avant envoi
            if attachments:
                fixed_attachments = _fix_image_orientations(attachments)
                msg_kwargs["attachments"] = fixed_attachments
            msg = MessageSchema(**msg_kwargs)
            await fm.send_message(msg)
            _log_email(session, code, all_emails_str, "succes", sujet=rendered_subject)
        except Exception as exc:
            logger.error("Erreur envoi email groupé [%s] → %s : %s", code, all_emails_str, exc)
            _log_email(session, code, all_emails_str, "erreur", erreur=str(exc)[:500])
    finally:
        # Nettoyer les fichiers temporaires EXIF
        if attachments:
            for fp in fixed_attachments:
                if fp not in attachments:
                    try:
                        os.unlink(fp)
                    except OSError:
                        pass
        if close_session:
            session.close()
