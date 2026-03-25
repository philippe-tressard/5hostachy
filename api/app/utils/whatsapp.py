"""Utilitaire envoi WhatsApp via whatsapp-bridge."""
import html
import json
import logging
import re
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


def _build_message(titre: str, contenu: str, urgente: bool, perimetre_cible: str | None, footer: str | None = None) -> str:
    """Construit le texte du message WhatsApp."""
    # Périmètre
    try:
        lieux = json.loads(perimetre_cible) if isinstance(perimetre_cible, str) else (perimetre_cible or [])
    except Exception:
        lieux = []
    if lieux and not (len(lieux) == 1 and lieux[0] == "résidence"):
        perimetre_label = ", ".join(lieux)
    else:
        perimetre_label = "Copropriété"

    if urgente:
        header = f"\U0001f6a8 URGENT \u2014 \U0001f539 {perimetre_label} \u2014 *{titre}*"
    else:
        header = f"\U0001f4e2 \U0001f539 {perimetre_label} \u2014 *{titre}*"

    # Contenu : convertir le formatage HTML en markdown WhatsApp
    # Gras : <b>, <strong>  → *texte*
    text = re.sub(r"<(b|strong)(\s[^>]*)?>(.+?)</(b|strong)>", r"*\3*", contenu, flags=re.IGNORECASE | re.DOTALL)
    # Italique : <i>, <em>  → _texte_
    text = re.sub(r"<(i|em)(\s[^>]*)?>(.+?)</(i|em)>", r"_\3_", text, flags=re.IGNORECASE | re.DOTALL)
    # Barré : <s>, <strike>, <del>  → ~texte~
    text = re.sub(r"<(s|strike|del)(\s[^>]*)?>(.+?)</(s|strike|del)>", r"~\3~", text, flags=re.IGNORECASE | re.DOTALL)
    # Saut de ligne : <br>, </p>
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    # Supprimer les balises HTML restantes
    text = re.sub(r"<[^>]+>", "", text)
    # Décoder les entités HTML (&nbsp; → espace, &amp; → &, etc.)
    text = html.unescape(text)
    # Remplacer les espaces insécables résiduels par des espaces normaux
    text = text.replace("\u00a0", " ")
    text = text.strip()

    footer = (footer or "").strip() or "— Conseil Syndical 5Hostachy"
    return f"{header}\n\n{text}\n\n{footer}"


def _resolve_image_url(image_url: str | None, config: dict) -> str | None:
    """Transforme une URL relative en URL absolue exploitable par le bridge."""
    if not image_url:
        return None
    if image_url.startswith('http://') or image_url.startswith('https://'):
        return image_url

    site_url = (config.get('site_url') or '').strip()
    if not site_url:
        return None
    return urljoin(f"{site_url.rstrip('/')}/", image_url.lstrip('/'))


def envoyer_whatsapp(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    image_url: str | None,
    config: dict,
) -> None:
    """Envoie un message sur le groupe WhatsApp. Silencieux en cas d'échec."""
    if config.get('whatsapp_enabled') != '1':
        return
    api_url = config.get('whatsapp_api_url', '').strip()
    api_key = config.get('whatsapp_api_key', '').strip()
    group_jid = config.get('whatsapp_group_jid', '').strip()
    if not api_url or not group_jid:
        logger.warning("WhatsApp activé mais whatsapp_api_url ou whatsapp_group_jid manquant.")
        return

    footer = config.get('whatsapp_footer', '').strip()
    message = _build_message(titre, contenu, urgente, perimetre_cible, footer)
    url = f"{api_url.rstrip('/')}/send"
    payload = {"number": group_jid, "text": message}
    resolved_image_url = _resolve_image_url(image_url, config)
    if resolved_image_url:
        payload["imageUrl"] = resolved_image_url
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Échec envoi WhatsApp : %s", exc)


def envoyer_whatsapp_avec_log(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    image_url: str | None,
    config: dict,
) -> None:
    """Envoie un message WhatsApp et crée un log (pour background tasks)."""
    from app.database import SessionLocal
    from app.models.core import WhatsAppLog
    from app.utils.whatsapp_scheduler import _prune_logs

    session = SessionLocal()
    try:
        footer = config.get('whatsapp_footer', '').strip()
        message = _build_message(titre, contenu, urgente, perimetre_cible, footer)
        log = WhatsAppLog(label=titre, message=message)
        try:
            envoyer_whatsapp(titre, contenu, urgente, perimetre_cible, image_url, config)
            log.statut = "envoyé"
            logger.info("Message WhatsApp '%s' envoyé.", titre)
        except Exception as exc:
            log.statut = "échec"
            log.erreur = str(exc)
            logger.warning("Échec envoi WhatsApp '%s': %s", titre, exc)
        
        session.add(log)
        session.commit()
        _prune_logs(session)
    except Exception as exc:
        logger.error("Erreur lors de l'enregistrement du log WhatsApp: %s", exc)
    finally:
        session.close()


def envoyer_whatsapp_raw(text: str, config: dict) -> dict:
    """Envoie un message brut sur le groupe WhatsApp. Lève une exception en cas d'échec."""
    api_url = config.get('whatsapp_api_url', '').strip()
    api_key = config.get('whatsapp_api_key', '').strip()
    group_jid = config.get('whatsapp_group_jid', '').strip()
    if not api_url or not group_jid:
        raise ValueError("whatsapp_api_url ou whatsapp_group_jid manquant.")

    url = f"{api_url.rstrip('/')}/send"
    payload = {"number": group_jid, "text": text}
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def get_whatsapp_status(config: dict) -> dict:
    """Interroge le bridge pour connaître l'état de la connexion WhatsApp."""
    api_url = config.get('whatsapp_api_url', '').strip()
    api_key = config.get('whatsapp_api_key', '').strip()
    if not api_url:
        raise ValueError("whatsapp_api_url manquant.")

    url = f"{api_url.rstrip('/')}/status"
    headers = {"x-api-key": api_key}

    with httpx.Client(timeout=5) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
