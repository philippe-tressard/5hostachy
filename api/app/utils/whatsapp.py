"""Utilitaire envoi WhatsApp via whatsapp-bridge."""
import base64
import html
import json
import logging
import re

import httpx

from app.utils.fichiers import chemins_locaux

logger = logging.getLogger(__name__)

#: Clés de `ConfigSite` qui décrivent le canal WhatsApp.
#:
#: Elles étaient recopiées dans QUATRE routers (publications, calendrier,
#: sondages, tickets) — et la copie de `publications` incluait `site_url` en
#: plus des autres, si bien que le lien « consulter l'application » ne pouvait
#: apparaître que dans les messages d'actualité. Une notion, une écriture
#: (`standards/02-factorisation.md` §2).
#:
#: `site_url` fait partie de l'ensemble : `_build_message_restreint` en a besoin
#: pour renvoyer vers l'application quand la publication est à public restreint.
CLES_CONFIG = frozenset({
    "whatsapp_enabled",
    "whatsapp_api_url",
    "whatsapp_api_key",
    "whatsapp_group_jid",
    "whatsapp_footer",
    "site_url",
})


def config_whatsapp(session, *cles_en_plus: str) -> dict:
    """Configuration WhatsApp lue en une requête, avec d'éventuelles clés de contexte.

    Les appelants ont souvent besoin, dans la même passe, de `site_nom` ou de
    `reference_copro` pour composer leur message : les demander ici évite une
    seconde requête et surtout une seconde liste de clés à maintenir.
    """
    from sqlmodel import select

    from app.models.core import ConfigSite

    voulues = CLES_CONFIG | set(cles_en_plus)
    lignes = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(voulues))).all()
    return {r.cle: r.valeur for r in lignes}


def whatsapp_actif(config: dict) -> bool:
    """Le canal est-il activé ? Seul `'1'` vaut oui — comparé à la main partout avant."""
    return config.get("whatsapp_enabled") == "1"


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


def _image_pour_bridge(image_url: str | None) -> str | None:
    """Photo interne → octets en base64, prêts pour le bridge. None si indisponible.

    ⚠️ On ne donne PLUS d'URL au bridge. Baileys allait alors chercher le fichier
    par l'internet public, ce qui exigeait que le dossier soit servi en anonyme :
    `/uploads/publications/` était le seul dans ce cas, et le seul pour cette
    raison. Le 10/08/2026, l'unification des galeries a fait atterrir les photos
    de publication dans le dossier authentifié — le bridge a reçu un 401 et
    l'annonce entière a disparu du groupe.

    L'API a le fichier sous la main : le lui faire retélécharger par le réseau
    public était un détour, et ce détour imposait de publier des photos que rien
    n'obligeait à rendre publiques. La résolution passe par `chemins_locaux`, qui
    refuse ce qui n'est pas à nous et ce qui sort du bac à sable.
    """
    if not image_url:
        return None
    chemins = chemins_locaux([image_url])
    if not chemins:
        logger.warning("Photo WhatsApp introuvable ou hors périmètre : %s", image_url)
        return None
    try:
        with open(chemins[0], "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except OSError as exc:
        logger.warning("Photo WhatsApp illisible (%s) : %s", image_url, exc)
        return None


def _is_restreint(public_cible: str | list | None) -> bool:
    """Retourne True si la publication n'est pas destinée à tous les résidents."""
    if public_cible is None:
        return False
    try:
        lst = json.loads(public_cible) if isinstance(public_cible, str) else public_cible
    except Exception:
        return False
    return "résidents" not in lst


def _build_message_restreint(
    titre: str,
    urgente: bool,
    perimetre_cible: str | None,
    site_url: str,
    pub_id: int | None,
    footer: str | None = None,
) -> str:
    """Construit un message WhatsApp court pour une publication à audience restreinte."""
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

    avertissement = (
        "\U0001f512 Cette publication est réservée à un public ciblé.\n"
        "Elle n'est pas accessible à tous les résidents.\n"
        "Si vous êtes concerné(e), connectez-vous sur 5Hostachy pour la consulter :"
    )
    lien = f"{site_url.rstrip('/')}/actualites"
    if pub_id is not None:
        lien += f"#pub-{pub_id}"

    footer = (footer or "").strip() or "— Conseil Syndical 5Hostachy"
    return f"{header}\n\n{avertissement}\n{lien}\n\n{footer}"


def envoyer_whatsapp(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    image_url: str | None,
    config: dict,
    public_cible: str | None = None,
    pub_id: int | None = None,
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
    url = f"{api_url.rstrip('/')}/send"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}

    if _is_restreint(public_cible):
        site_url = (config.get('site_url') or '').strip()
        message = _build_message_restreint(titre, urgente, perimetre_cible, site_url, pub_id, footer)
        payload = {"number": group_jid, "text": message}
    else:
        message = _build_message(titre, contenu, urgente, perimetre_cible, footer)
        payload = {"number": group_jid, "text": message}
        image_b64 = _image_pour_bridge(image_url)
        if image_b64:
            payload["imageBase64"] = image_b64
        elif image_url:
            # La photo existe mais n'a pas pu être jointe. Le message part quand
            # même — un envoi perdu est bien pire qu'un envoi sans image — et il
            # dit où la voir plutôt que de laisser croire qu'il n'y en a pas.
            lien = (config.get('site_url') or '').strip().rstrip('/')
            if lien:
                payload["text"] += (
                    "\n\n\U0001F4F7 Photos à voir sur le site : "
                    f"{lien}/actualites"
                )

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning("Échec envoi WhatsApp : %s", exc)
        raise


def envoyer_whatsapp_avec_log(
    titre: str,
    contenu: str,
    urgente: bool,
    perimetre_cible: str | None,
    image_url: str | None,
    config: dict,
    public_cible: str | None = None,
    pub_id: int | None = None,
) -> None:
    """Envoie un message WhatsApp et crée un log (pour background tasks)."""
    from app.database import SessionLocal
    from app.models.core import WhatsAppLog
    from app.utils.whatsapp_scheduler import _prune_logs

    session = SessionLocal()
    try:
        footer = config.get('whatsapp_footer', '').strip()
        if _is_restreint(public_cible):
            site_url = (config.get('site_url') or '').strip()
            message = _build_message_restreint(titre, urgente, perimetre_cible, site_url, pub_id, footer)
        else:
            message = _build_message(titre, contenu, urgente, perimetre_cible, footer)
        log = WhatsAppLog(label=titre, message=message)
        try:
            envoyer_whatsapp(titre, contenu, urgente, perimetre_cible, image_url, config, public_cible, pub_id)
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
