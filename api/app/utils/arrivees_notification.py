"""Les arrivées par notification — qui vient par un courriel, qui par le groupe WhatsApp (#1634).

## Pourquoi (04/10/2026)

Le site envoie des courriels et diffuse sur le canal WhatsApp de la résidence
(`utils/diffusion`). On ne savait pas lequel fait VENIR les résidents : une
notification que personne n'ouvre est du bruit.

## L'étiquette — UNE fonction, posée là où le message se compose

`etiqueter_lien` ajoute `src=<canal>` (`courriel:<code du modèle>` ou
`whatsapp`) aux liens du site. Elle est appelée à deux endroits, ceux où chaque
message se COMPOSE pour tous ses modèles : `email.composer_email` (la seule
composition des courriels, aperçu compris) et `whatsapp_message.construire_message`.
Le texte des modèles en base ne change pas : aucune migration, aucun modèle
réécrit, et un modèle ajouté demain est étiqueté sans qu'on y pense.

Ce qu'elle ne fait JAMAIS :
- étiqueter un lien qui porte un jeton (`token=`) — un lien à usage unique
  (mot de passe oublié, vérification d'adresse) reste tel qu'il a été émis
  (`standards/03` §5 bis) ; et les courriels des comptes (`MODELES_SANS_ETIQUETTE`)
  ne sont pas étiquetés du tout ;
- étiqueter un lien d'un autre site, une adresse `mailto:`, ou deux fois ;
- porter une donnée personnelle : un canal et un code de modèle, rien d'autre —
  ni adresse, ni identifiant de destinataire.

## La lecture

Le navigateur lit l'étiquette à l'arrivée, l'envoie comme `detail` de la vue de
page (`front/src/lib/arrivees.ts`, par `trackEvent`, donc sous le refus du
profil), puis la retire de l'adresse affichée. Les évènements vivent 30 jours :
`synthese_arrivees` les compte par canal et par modèle, et les rapporte aux
messages envoyés (`historique_email`, une ligne par message — un envoi groupé
en est une ; `whatsapp_log`).
"""

from __future__ import annotations

import html
import re
from datetime import date
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.core import HistoriqueEmail, ModeleEmail, TelemetryEvent
from app.models.whatsapp import WhatsAppLog
from app.utils import horloge

#: Le paramètre de l'étiquette. ⚠️ Tenu à la main, avec les deux canaux et la
#: forme d'un code, dans `front/src/lib/arrivees.ts` : aucun fichier partagé.
PARAMETRE_SOURCE = "src"
SOURCE_COURRIEL = "courriel"
SOURCE_WHATSAPP = "whatsapp"
#: Une étiquette valide : un canal, et pour un courriel le code de son modèle.
MOTIF_SOURCE = re.compile(r"(courriel|whatsapp)(?::([a-z0-9_]{1,40}))?")

#: Les courriels des COMPTES — ils partent hors de toute session (inscription,
#: mot de passe oublié) : rien à mesurer, et leurs liens sont à usage unique.
MODELES_SANS_ETIQUETTE = frozenset({"reinitialisation_mdp", "verification_email"})
#: Un lien qui porte l'un de ces paramètres est à usage unique.
PARAMETRES_DE_JETON = frozenset({"token", "jeton"})

_HREF = re.compile(r'(href\s*=\s*")([^"]*)(")', re.IGNORECASE)


def source_courriel(code: str | None) -> str:
    """L'étiquette d'un courriel : `courriel:<code>`, ou le canal seul si le code n'est pas un slug."""
    etiquette = f"{SOURCE_COURRIEL}:{code}" if code else SOURCE_COURRIEL
    return etiquette if MOTIF_SOURCE.fullmatch(etiquette) else SOURCE_COURRIEL


def _du_site(lien: str, site_url: str) -> bool:
    if lien.startswith("/") and not lien.startswith("//"):
        return True
    site = site_url.rstrip("/")
    return bool(site) and (lien == site or lien.startswith((site + "/", site + "?", site + "#")))


def etiqueter_lien(lien: str, source: str, site_url: str) -> str:
    """Le lien, avec `src=<source>` avant son ancre — ou tel quel s'il ne doit pas l'être."""
    if not lien or not _du_site(lien, site_url):
        return lien
    morceaux = urlsplit(lien)
    parametres = {cle for cle, _ in parse_qsl(morceaux.query, keep_blank_values=True)}
    if parametres & (PARAMETRES_DE_JETON | {PARAMETRE_SOURCE}):
        return lien
    requete = f"{morceaux.query}&" if morceaux.query else ""
    chemin = morceaux.path or ("/" if morceaux.netloc else "")
    return urlunsplit(
        (
            morceaux.scheme,
            morceaux.netloc,
            chemin,
            f"{requete}{PARAMETRE_SOURCE}={source}",
            morceaux.fragment,
        )
    )


def etiqueter_courriel(corps_html: str, site_url: str, code: str | None) -> str:
    """Étiquette chaque lien du site d'un courriel composé — sauf les courriels des comptes."""
    if code in MODELES_SANS_ETIQUETTE:
        return corps_html
    source = source_courriel(code)

    def _un(m: re.Match) -> str:
        brut = html.unescape(m.group(2))
        etiquete = etiqueter_lien(brut, source, site_url)
        if etiquete == brut:
            return m.group(0)
        return m.group(1) + etiquete.replace("&", "&amp;") + m.group(3)

    return _HREF.sub(_un, corps_html)


def synthese_arrivees(session: Session, depuis: date, filtre: list | None = None) -> list[dict]:
    """Les vues arrivées par une notification depuis `depuis`, par canal et modèle, et leurs envois.

    `filtre` : les conditions de la lecture sur les évènements (le gestionnaire
    du site écarté, `telemetrie_lecture.Lecture.evenements`). Un modèle envoyé
    sur la période et jamais suivi a sa ligne, à zéro arrivée.
    """
    debut = horloge.debut_du_jour_utc(depuis)
    vues = session.exec(
        select(
            TelemetryEvent.detail,
            func.count(),
            func.count(func.distinct(TelemetryEvent.user_id)),
        )
        .where(
            TelemetryEvent.cree_le >= debut,
            TelemetryEvent.action == "view",
            TelemetryEvent.detail.isnot(None),
            *(filtre or []),
        )
        .group_by(TelemetryEvent.detail)
    ).all()
    lignes: dict[tuple[str, str | None], dict] = {}
    for detail, arrivees, comptes in vues:
        m = MOTIF_SOURCE.fullmatch(detail or "")
        if not m:
            continue
        ligne = lignes.setdefault(
            (m.group(1), m.group(2)),
            {"canal": m.group(1), "modele": m.group(2), "arrivees": 0, "comptes": 0},
        )
        ligne["arrivees"] += arrivees
        ligne["comptes"] += comptes

    courriels = session.exec(
        select(HistoriqueEmail.code, func.count())
        .where(HistoriqueEmail.cree_le >= debut, HistoriqueEmail.statut == "succes")
        .group_by(HistoriqueEmail.code)
    ).all()
    envois: dict[tuple[str, str | None], int] = {
        (SOURCE_COURRIEL, code): n for code, n in courriels if code not in MODELES_SANS_ETIQUETTE
    }
    groupe = session.exec(
        select(func.count()).where(WhatsAppLog.envoye_le >= debut, WhatsAppLog.statut == "envoyé")
    ).one()
    if groupe:
        envois[(SOURCE_WHATSAPP, None)] = groupe
    for cle in envois:
        lignes.setdefault(cle, {"canal": cle[0], "modele": cle[1], "arrivees": 0, "comptes": 0})

    libelles = dict(session.exec(select(ModeleEmail.code, ModeleEmail.libelle)).all())
    rendu = [
        {
            **ligne,
            "libelle": libelles.get(ligne["modele"]) if ligne["modele"] else None,
            "envois": envois.get(cle),
        }
        for cle, ligne in lignes.items()
    ]
    rendu.sort(key=lambda r: (-r["arrivees"], -(r["envois"] or 0), r["canal"], r["modele"] or ""))
    return [
        {k: r[k] for k in ("canal", "modele", "libelle", "arrivees", "comptes", "envois")}
        for r in rendu
    ]
