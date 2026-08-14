"""Utilitaire envoi WhatsApp via whatsapp-bridge."""
import base64
import html
import json
import logging
import re
from typing import Any, Callable

import httpx

from app.utils.fichiers import chemins_locaux

logger = logging.getLogger(__name__)


class EnvoiIncertain(Exception):
    """L'envoi n'a pas été acquitté — et rien ne dit qu'il n'a pas eu lieu.

    À distinguer d'un échec : un **échec** est établi (la requête n'a jamais
    atteint le bridge, donc rien n'a pu être remis au groupe), un envoi
    **incertain** a peut-être été remis. Les deux ne se traitent pas pareil : on
    rejoue le premier, jamais le second.
    """


#: Verdicts d'un envoi, tels qu'ils sont stockés dans `WhatsAppLog.statut`.
STATUT_ENVOYE = "envoyé"
STATUT_ECHEC = "échec"
STATUT_INCERTAIN = "incertain"
STATUT_EN_COURS = "en cours"

#: Verdicts qui interdisent de rejouer l'envoi.
#:
#: `en cours` en fait partie : une tentative engagée dont on n'a jamais vu la fin
#: (redémarrage du conteneur en plein envoi) est, du point de vue du groupe,
#: exactement un envoi incertain.
STATUTS_NON_REJOUABLES = frozenset({STATUT_ENVOYE, STATUT_INCERTAIN, STATUT_EN_COURS})

#: Délai d'attente d'une réponse du bridge.
#:
#: Le bridge chiffre le message pour chaque appareil du groupe et resynchronise
#: au besoin les sessions Signal : sur un Raspberry Pi, la réponse peut demander
#: bien plus que les 15 s d'origine. Ce délai ne garantit rien — il ne fait que
#: rendre le verdict « incertain » rare. C'est `EnvoiIncertain`, et non ce
#: nombre, qui protège du doublon.
TIMEOUT_ENVOI = 60


def _poster_au_bridge(url: str, payload: dict, headers: dict, timeout: float = TIMEOUT_ENVOI):
    """POST vers le bridge, en distinguant l'échec établi du résultat inconnu.

    Un client HTTP qui n'obtient pas de réponse ne sait **rien** de ce que le
    serveur a fait. Traiter ce silence comme « rien n'est parti » puis rejouer,
    c'est fabriquer des doublons dès que le bridge est lent : le 14/08/2026,
    trois exemplaires du message « Encombrants » sont partis dans le groupe pour
    cette seule raison — le bridge dépassait le délai d'attente mais délivrait.
    Un doublon dans un groupe de copropriétaires ne se retire pas.

    Les cas où l'on **sait** que rien n'est sorti sont énumérés ici ; tout le
    reste est incertain par défaut (`standards/04-fiabilite-des-controles.md` :
    un résultat qu'on ne peut pas constater se rapporte INCONNU, jamais autre
    chose — ici, pas davantage KO que OK).
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
        #  Aucune connexion n'a été établie : la requête n'a jamais atteint le
        #  bridge, le groupe n'a rien reçu. Rejouer est sûr.
        raise
    except httpx.HTTPStatusError as exc:
        #  Le bridge a répondu et refusé. 4xx : requête invalide (clé d'API,
        #  destinataire) — elle n'a pas été traitée. 5xx : il a échoué en cours
        #  de route, sans dire de quel côté de l'envoi.
        if exc.response.status_code < 500:
            raise
        raise EnvoiIncertain(f"réponse {exc.response.status_code} du bridge") from exc
    except httpx.HTTPError as exc:
        #  Délai dépassé après émission, coupure en cours d'échange, réponse
        #  tronquée : le message a pu partir.
        raise EnvoiIncertain(str(exc) or exc.__class__.__name__) from exc


def verdict_envoi(envoi: Callable[[], Any]) -> tuple[str, str | None]:
    """Exécute `envoi` et rend `(statut, erreur)` — jamais « échec » sur un doute.

    Une notion, une écriture : les trois chemins d'envoi (message planifié,
    publication, test manuel) qualifiaient chacun leur résultat avec un
    `except Exception` qui écrivait « échec ». L'historique de l'administration
    affirmait donc qu'un message n'était pas parti alors qu'il l'était.
    """
    try:
        envoi()
        return STATUT_ENVOYE, None
    except EnvoiIncertain as exc:
        return STATUT_INCERTAIN, str(exc)
    except Exception as exc:
        return STATUT_ECHEC, str(exc)

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
        _poster_au_bridge(url, payload, headers)
    except EnvoiIncertain as exc:
        logger.warning("Envoi WhatsApp au résultat inconnu : %s", exc)
        raise
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
        log.statut, log.erreur = verdict_envoi(
            lambda: envoyer_whatsapp(
                titre, contenu, urgente, perimetre_cible, image_url, config, public_cible, pub_id
            )
        )
        if log.statut == STATUT_ENVOYE:
            logger.info("Message WhatsApp '%s' envoyé.", titre)
        else:
            logger.warning("Envoi WhatsApp '%s' — %s : %s", titre, log.statut, log.erreur)

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

    return _poster_au_bridge(url, payload, headers).json()


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
