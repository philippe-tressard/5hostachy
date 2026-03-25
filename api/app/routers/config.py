"""
Configuration du site — paramètres admin persistants en base de données.
Remplace le localStorage pour permettre la synchronisation multi-appareils.
"""
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import ConfigSite, Utilisateur
from app.seed import DEFAULT_LEGAL

router = APIRouter(prefix="/config", tags=["config"])

_LEGAL_KEYS = {'mentions_legales', 'politique_confidentialite'}
_PRIVATE_KEYS = {'whatsapp_api_key', 'smtp_password'}


@router.get("", response_model=Dict[str, str])
def get_config(session: Session = Depends(get_session)):
    """Retourne les clés de configuration UI (public). Exclut les contenus légaux et les clés privées."""
    rows = session.exec(select(ConfigSite)).all()
    return {r.cle: r.valeur for r in rows if r.cle not in _LEGAL_KEYS and r.cle not in _PRIVATE_KEYS}


@router.get("/admin", response_model=Dict[str, str])
def get_config_admin(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Retourne toutes les clés de configuration, y compris les clés privées (admin uniquement)."""
    rows = session.exec(select(ConfigSite)).all()
    return {r.cle: r.valeur for r in rows if r.cle not in _LEGAL_KEYS}


@router.get("/legal", response_model=Dict[str, str])
def get_legal_config(session: Session = Depends(get_session)):
    """Retourne uniquement les contenus des pages légales (public).
    Si une clé est absente de la BDD, renvoie le contenu par défaut."""
    rows = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(_LEGAL_KEYS))).all()
    result = {k: DEFAULT_LEGAL[k] for k in _LEGAL_KEYS if k in DEFAULT_LEGAL}
    result.update({r.cle: r.valeur for r in rows if r.valeur})
    return result


@router.put("")
def save_config(
    data: Dict[str, str],
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Sauvegarde ou met à jour des clés de configuration (admin uniquement)."""
    for cle, valeur in data.items():
        existing = session.get(ConfigSite, cle)
        if existing:
            existing.valeur = str(valeur)
            session.add(existing)
        else:
            session.add(ConfigSite(cle=cle, valeur=str(valeur)))
    session.commit()
    return {"ok": True}


# ── WhatsApp scheduled messages ──────────────────────────────────────

class WhatsAppScheduledUpdate(BaseModel):
    label: str | None = None
    message: str | None = None
    cron_rule: str | None = None
    enabled: bool | None = None


@router.get("/whatsapp-scheduled")
def list_whatsapp_scheduled(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Liste les messages WhatsApp planifiés."""
    from app.models.core import WhatsAppScheduled
    rows = session.exec(select(WhatsAppScheduled).order_by(WhatsAppScheduled.id)).all()
    return [
        {"id": r.id, "label": r.label, "message": r.message, "cron_rule": r.cron_rule,
         "enabled": r.enabled, "mis_a_jour_le": r.mis_a_jour_le.isoformat() if r.mis_a_jour_le else None}
        for r in rows
    ]


@router.put("/whatsapp-scheduled/{item_id}")
def update_whatsapp_scheduled(
    item_id: int,
    data: WhatsAppScheduledUpdate,
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Met à jour un message WhatsApp planifié."""
    from app.models.core import WhatsAppScheduled
    from datetime import datetime as _dt
    item = session.get(WhatsAppScheduled, item_id)
    if not item:
        raise HTTPException(404, "Message planifié introuvable.")
    if data.label is not None:
        item.label = data.label
    if data.message is not None:
        item.message = data.message
    if data.cron_rule is not None:
        item.cron_rule = data.cron_rule
    if data.enabled is not None:
        item.enabled = data.enabled
    item.mis_a_jour_le = _dt.utcnow()
    session.add(item)
    session.commit()
    return {"ok": True}


@router.get("/whatsapp-logs")
def list_whatsapp_logs(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Retourne les 6 derniers messages WhatsApp envoyés."""
    from app.models.core import WhatsAppLog
    rows = session.exec(
        select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc()).limit(6)
    ).all()
    return [
        {"id": r.id, "label": r.label, "message": r.message, "statut": r.statut,
         "erreur": r.erreur, "envoye_le": r.envoye_le.isoformat() if r.envoye_le else None}
        for r in rows
    ]


class WhatsAppTestPayload(BaseModel):
    message: str


@router.post("/whatsapp-test")
def whatsapp_test(
    payload: WhatsAppTestPayload,
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Envoie un message de test sur le groupe WhatsApp (admin uniquement)."""
    from app.utils.whatsapp import envoyer_whatsapp_raw
    from app.models.core import WhatsAppLog

    rows = session.exec(select(ConfigSite)).all()
    config = {r.cle: r.valeur for r in rows}

    text = (payload.message or "").strip()
    if not text:
        raise HTTPException(400, "Le message ne peut pas être vide.")

    log = WhatsAppLog(label="Test manuel", message=text)
    try:
        result = envoyer_whatsapp_raw(text, config)
        log.statut = "envoyé"
        session.add(log)
        session.commit()
        # Garder seulement les 6 derniers
        from app.utils.whatsapp_scheduler import _prune_logs
        _prune_logs(session)
        return {"ok": True, "message": "Message envoyé sur le groupe WhatsApp.", "detail": result}
    except Exception as e:
        log.statut = "échec"
        log.erreur = str(e)
        session.add(log)
        session.commit()
        raise HTTPException(500, f"Échec de l'envoi : {e}")


@router.get("/whatsapp-status")
def whatsapp_status(
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Retourne l'état de la connexion WhatsApp (admin uniquement)."""
    from app.utils.whatsapp import get_whatsapp_status

    rows = session.exec(select(ConfigSite)).all()
    config = {r.cle: r.valeur for r in rows}

    try:
        return get_whatsapp_status(config)
    except Exception as e:
        raise HTTPException(500, f"Impossible de joindre le bridge : {e}")


class SmtpTestPayload(BaseModel):
    email: EmailStr


@router.post("/smtp-test")
async def smtp_test(
    payload: SmtpTestPayload,
    user: Utilisateur = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Envoie un e-mail de test à l'adresse fournie en utilisant la config SMTP actuelle (admin uniquement)."""
    from app.config import get_settings
    from app.utils.email import _get_smtp_config

    settings = get_settings()
    smtp_cfg = _get_smtp_config(session)

    if smtp_cfg.get('smtp_enabled') != '1' and not settings.mail_enabled:
        raise HTTPException(400, "L'envoi d'e-mails est désactivé. Activez-le avant de tester.")

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
        msg = MessageSchema(
            subject="[5Hostachy] Test de configuration SMTP",
            recipients=[payload.email],
            body=(
                "<p>Bonjour,</p>"
                "<p>Ceci est un e-mail de test envoyé depuis l'interface d'administration de <strong>5Hostachy</strong>.</p>"
                "<p>Si vous recevez ce message, votre configuration SMTP est correctement configurée ✅</p>"
                "<p style='color:#64748b;font-size:.85em'>— 5Hostachy</p>"
            ),
            subtype="html",
        )
        await fm.send_message(msg)
        return {"ok": True, "message": f"E-mail de test envoyé à {payload.email}"}
    except Exception as e:
        raise HTTPException(500, f"Échec de l'envoi : {e}")
