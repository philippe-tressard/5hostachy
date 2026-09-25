"""Ce que devient le TEXTE d'une réponse reçue par courriel sur une affaire (#1322).

La relève (`courriel_boite`) décide si un message rejoint un fil ; ce module dit
**ce qui y entre** : le texte, sa date, et ce que l'assistant en a fait.

## Demandé le 25/09/2026

> « que le mail soit bien formaté, daté, […] avec les lignes inutiles du message
>   d'origine retirées, les lignes blanches etc… juste la réponse utile »

Arbitré : la mise en forme est **automatique** à la relève, le **texte reçu est
conservé** (« Message d'origine » dans la Suite), et la Suite est **datée de
l'envoi** du courriel.

## Ce qui ne se perd jamais

`_sans_citation` retire d'abord, sans IA, le message cité. L'assistant ne voit
que ce reste — ce qu'il faut pour le mettre en forme, et rien de plus : le fil
cité porte souvent les données d'autres personnes. Si l'usage est coupé, non
réglé, en échec, ou s'il rend quelque chose de suspect (vide, ou plus long que
ce qu'on lui a donné : il n'a rien à ajouter), le texte nettoyé sans IA entre
dans le fil. **Une réponse du syndic n'est jamais perdue à cause de l'assistant.**
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime

from sqlmodel import Session

from app.utils import horloge

logger = logging.getLogger(__name__)

USAGE_REPONSE_COURRIEL = "reponse_courriel"

#: Le prompt d'origine de l'usage — modifiable depuis l'administration.
CONSIGNE = (
    "Tu reçois le texte d'une réponse envoyée par courriel sur une affaire de "
    "copropriété, le plus souvent par le syndic. Rends UNIQUEMENT la réponse utile, "
    "mise en forme :\n"
    "- retire la signature, les coordonnées, les mentions légales ou de "
    "confidentialité, les formules automatiques et tout reste du message cité ;\n"
    "- retire les lignes vides superflues ; garde les paragraphes et les listes de "
    "l'auteur ;\n"
    "- ne résume pas, ne reformule pas, n'ajoute rien : les mots sont ceux de "
    "l'auteur, seule la présentation change ;\n"
    "- rends du texte simple, sans balises ni Markdown, sans introduction ni "
    "commentaire.\n"
    "Si rien d'utile ne reste, rends une réponse vide."
)

#: Le texte reçu conservé, borné : un fil transféré peut peser des centaines de
#: kilo-octets, et ce n'est pas la base qui doit en porter l'historique entier.
MAX_ORIGINE = 20_000

#: Une date d'envoi plus loin dans le futur est une horloge fausse chez
#: l'expéditeur : on date alors de la relève.
TOLERANCE_FUTUR = timedelta(minutes=5)


def date_d_envoi(entete: str | None) -> datetime | None:
    """L'en-tête `Date` en UTC NAÏF — la forme des dates en base — ou None.

    🔴 La relève faisait `parsedate_to_datetime(...).replace(tzinfo=None)` : elle
    JETAIT le fuseau sans convertir. « 18:00 +0200 » devenait 18:00 UTC, deux
    heures trop tard — et le plancher de la relève se comparait à cette date
    fausse. Un en-tête sans fuseau est pris pour de l'UTC (RFC 5322 : `-0000`).
    """
    try:
        d = parsedate_to_datetime(entete or "")
    except (TypeError, ValueError, IndexError):
        return None
    if d is None:
        return None
    if d.tzinfo is not None:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d


def moment_de_la_suite(envoye_le: datetime | None, maintenant: datetime | None = None) -> datetime:
    """La date de la Suite : celle de l'envoi, sauf si elle est absente ou future."""
    maintenant = maintenant or horloge.maintenant()
    if envoye_le is None or envoye_le > maintenant + TOLERANCE_FUTUR:
        return maintenant
    return envoye_le


@dataclass(frozen=True)
class Texte:
    """Ce qui entre dans le fil."""

    contenu: str
    #: Le texte reçu, quand l'assistant l'a mis en forme ; None sinon.
    origine: str | None
    assiste: bool


def mettre_en_forme(session: Session, nettoye: str, recu: str) -> Texte:
    """La réponse utile, mise en forme par l'assistant si l'usage est prêt.

    `nettoye` : le texte sans citation (`_sans_citation`), seul envoyé au modèle.
    `recu` : le texte lisible du courriel, conservé quand l'assistant a travaillé.

    ⚠️ Synchrone : la relève tourne sous `BackgroundScheduler`, sans boucle
    d'événements — `asyncio.run` y est sûr (`health_monitor` fait de même).
    """
    repli = Texte(contenu=nettoye, origine=None, assiste=False)
    if not nettoye:
        return repli
    from app.utils.llm import ErreurLLM, demander

    try:
        reponse = asyncio.run(demander(session, usage=USAGE_REPONSE_COURRIEL, message=nettoye))
    except ErreurLLM as exc:
        #  Usage coupé ou non réglé : le cas nominal tant que l'administration ne
        #  l'a pas activé. Une ligne d'information, pas une alerte.
        logger.info("Réponse par courriel : mise en forme non appliquée (%s)", exc)
        return repli
    except Exception as exc:  # noqa: BLE001 — la relève ne doit jamais perdre la réponse
        logger.warning("Réponse par courriel : mise en forme en échec (%s)", type(exc).__name__)
        return repli
    propre = (reponse.texte or "").strip()
    if not propre or len(propre) > len(nettoye) + max(40, len(nettoye) // 10):
        #  Vide, ou plus long que ce qu'on lui a donné : il a ajouté quelque chose.
        logger.warning(
            "Réponse par courriel : mise en forme écartée (%d caractères pour %d)",
            len(propre),
            len(nettoye),
        )
        return repli
    return Texte(contenu=propre, origine=(recu or nettoye)[:MAX_ORIGINE], assiste=True)


def contenu_de_la_suite(
    expediteur: str, nom_du_compte: str, envoye_le: datetime, texte: str
) -> str:
    """Le HTML de la Suite : « Réponse de … le … » en italique, puis le texte.

    La ligne d'en-tête est écrite par le CODE, jamais par le modèle (arbitré le
    25/09/2026) : un nom et une date lus dans l'en-tête ne s'inventent pas. Le nom
    est celui que le courriel affiche (« Jean Martin <jm@…> »), à défaut celui du
    compte ; la date, l'envoi en heure de Paris.

    🔴 Le texte est ÉCHAPPÉ : c'est un courriel reçu, et `safeDescription` ne
    ré-échappe pas une chaîne qui commence par une balise.
    """
    from html import escape

    from app.utils.dates_fr import datetime_longue_paris

    nom = parseaddr(expediteur or "")[0].strip() or nom_du_compte
    entete = f"<p><em>Réponse de {escape(nom, quote=False)} le {datetime_longue_paris(envoye_le)}</em></p>"
    paragraphes = [p.strip() for p in re.split(r"\n\s*\n", texte) if p.strip()]
    corps = "".join(
        "<p>" + "<br>".join(escape(ligne.strip(), quote=False) for ligne in p.splitlines()) + "</p>"
        for p in paragraphes
    )
    return entete + corps


def suite_de_reponse(
    session: Session, ticket_id: int, auteur, expediteur: str, corps: str, envoye_le
):
    """La Suite à ajouter au fil, ou None si le message n'a rien d'utile."""
    from app.models.core import TicketEvolution
    from app.utils.courriel_decodage import _sans_citation
    from app.utils.noms import nom_affiche

    texte = mettre_en_forme(session, _sans_citation(corps), corps)
    if not texte.contenu:
        return None
    quand = moment_de_la_suite(envoye_le)
    return TicketEvolution(
        ticket_id=ticket_id,
        type="commentaire",
        contenu=contenu_de_la_suite(
            expediteur, nom_affiche(auteur.prenom, auteur.nom), quand, texte.contenu
        ),
        contenu_origine=texte.origine,
        assiste_ia=texte.assiste,
        auteur_id=auteur.id,
        cree_le=quand,
    )
