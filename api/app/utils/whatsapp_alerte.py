"""Prévenir un humain quand un message WhatsApp n'est pas arrivé — une écriture.

Un envoi en échec était **muet** partout sauf pour le message mensuel planifié :
`whatsapp_scheduler._alerter` était le seul à prévenir, et les envois déclenchés
par un geste (ticket, actualité, événement, annonce de hall, sondage) ne
prévenaient personne. Le 19/09/2026, deux partages de ticket ont été refusés par
le bridge ; l'utilisateur l'a découvert en regardant son fil WhatsApp, pas par une
alerte (#1057).

C'est la famille « un contrôle sans destinataire est un contrôle mort »
(`standards/04-fiabilite-des-controles.md` §7) : l'échec était mesuré, enregistré,
lisible dans *Admin → WhatsApp → Historique*… et personne n'allait le lire.

## Pourquoi cette fonction est ici et pas chez l'un des deux appelants

Une règle rangée chez un appelant est recopiée par le suivant
(`standards/02-factorisation.md` §4 sexies). La conduite à tenir sur un envoi
**incertain** — ne jamais rejouer, aller regarder le groupe — est ce qui protège
du doublon du 14/08/2026 : elle ne doit exister qu'à un seul endroit.

## Pas de temporisation, et c'est délibéré

Un envoi WhatsApp est un **geste**, pas un battement : il n'y en a que quelques-uns
par semaine, tous déclenchés par une personne. Une alerte par geste raté est donc
proportionnée. Si un jour un envoi devient périodique, c'est à ce moment-là qu'une
temporisation se posera — pas avant.
"""

import logging

from sqlmodel import Session

from app.utils.whatsapp import STATUT_INCERTAIN

logger = logging.getLogger(__name__)


def alerter_envoi(
    session: Session,
    label: str,
    statut: str,
    erreur: str | None,
    *,
    precision: str = "",
) -> None:
    """Alerte e-mail : un message WhatsApp n'est pas arrivé, ou peut-être si.

    `precision` complète le constat d'échec avec ce que seul l'appelant sait
    (la fenêtre de rattrapage d'un message planifié, par exemple).

    Le cas « incertain » demande une action que la machine ne peut pas prendre à
    la place d'un humain : aller regarder le groupe. Rejouer d'autorité, c'est ce
    qui a produit trois exemplaires le 14/08/2026.

    Ne lève jamais : prévenir est un effet de bord de l'envoi, et un serveur de
    messagerie indisponible ne doit pas empêcher d'enregistrer ce qui s'est passé.
    """
    from app.utils.email import get_site_manager_notification_email
    from app.utils.health_monitor import _send_alert

    try:
        if statut == STATUT_INCERTAIN:
            constat = (
                f"Message WhatsApp « {label} » : le bridge n'a pas acquitté "
                "l'envoi, mais le message est peut-être arrivé dans le groupe.\n"
                "    → Vérifier le groupe WhatsApp. S'il n'y est pas, le renvoyer depuis "
                "Admin → WhatsApp. Aucun rejeu automatique n'aura lieu : il ferait doublon."
            )
        else:
            constat = (
                f"Message WhatsApp « {label} » non envoyé.{precision}\n"
                f"    Statut : {statut}\n"
                "    → Rien n'est parti : le renvoyer depuis l'écran d'origine est sans risque."
            )
        issue = f"{constat}\n    Dernière erreur : {erreur or 'inconnue'}"

        to, _ = get_site_manager_notification_email(session)
        if not to:
            logger.warning(
                "Envoi WhatsApp '%s' au statut « %s » — pas d'email admin configuré "
                "pour alerter. %s",
                label,
                statut,
                erreur or "",
            )
            return
        _send_alert(to, [issue], session)
    except Exception as exc:  # noqa: BLE001 — l'alerte ne doit pas casser l'envoi
        logger.warning("Alerte d'envoi WhatsApp non partie (%s) : %s", label, exc)
