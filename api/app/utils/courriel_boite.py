"""La relève de la boîte des réponses — le TUYAU, et rien que le tuyau (#703).

## Ce fichier ne décide de rien

Il ouvre la boîte, lit les messages non traités, appelle
`courriel_ingestion.examiner`, et applique le verdict. La décision est ailleurs,
et c'est délibéré : elle s'y éprouve sur des messages écrits à la main, y compris
hostiles, sans réseau ni base.

## Ce qui se passe pour chaque message

    IGNORE   → marqué lu, rien d'autre. Un prospectus ne doit produire aucun bruit.
    REFUSE   → NOTIFICATION au conseil syndical, rien dans le ticket.
    ACCEPTE  → une entrée dans le fil du ticket, signée du compte de l'expéditeur.

🔴 **Un message accepté dont l'expéditeur n'a pas de compte est REFUSÉ.**
`TicketEvolution.auteur_id` est une clé obligatoire vers `utilisateur` : écrire
quand même aurait demandé soit un compte de service — qui signerait « 5Hostachy »
un texte écrit par un tiers —, soit de rendre la colonne nullable, ce qui touche
tout le fil de tous les tickets. Les deux sont des décisions lourdes prises pour
un cas rare. Le conseil syndical est prévenu, et recopie s'il le veut : c'est un
clic de plus, pas une donnée perdue.

## Le silence est ce qui rend un filtre dangereux

Chaque refus produit une notification nommant le ticket et **la raison**. Un
filtre qu'on n'entend jamais finit par être cru parfait, et il l'est d'autant
moins que personne ne le regarde.

## La configuration

Tout vit dans `ConfigSite`, administrable, et **rien n'est activé par défaut** :
`imap_enabled` à faux, la relève ne tourne pas. Les identifiants sont ceux de la
boîte d'envoi — c'est le même compte chez l'hébergeur —, mais le serveur IMAP est
distinct du SMTP et se déclare à part.
"""
from __future__ import annotations

import email
import imaplib
import logging
from datetime import datetime
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from sqlmodel import Session, select

from app.models.core import ConfigSite, Notification, Ticket, TicketEvolution, Utilisateur
from app.utils.courriel_ingestion import ACCEPTE, IGNORE, REFUSE, PLANCHER_PAR_DEFAUT, examiner

logger = logging.getLogger(__name__)

#: Les clés lues dans `ConfigSite`. `imap_enabled` d'abord : sans elle, rien.
_CLES = {
    "imap_enabled", "imap_server", "imap_port", "imap_username",
    "imap_password", "imap_dossier", "imap_plancher",
}

#: Un corps de réponse dépasse rarement quelques lignes utiles ; au-delà c'est la
#: citation du message précédent. Tronqué pour ne pas recopier tout un fil dans
#: le ticket à chaque échange.
MAX_CORPS = 4000


def config_imap(session: Session) -> dict:
    lignes = session.exec(select(ConfigSite).where(ConfigSite.cle.in_(_CLES))).all()
    return {r.cle: r.valeur for r in lignes}


def _texte(valeur) -> str:
    """Un en-tête décodé, quel que soit son encodage MIME."""
    if not valeur:
        return ""
    try:
        return str(make_header(decode_header(valeur)))
    except Exception:
        return str(valeur)


def _corps_lisible(message) -> str:
    """Le texte de la réponse, en clair.

    On préfère la partie `text/plain` : elle existe presque toujours, et elle
    évite d'avoir à assainir du HTML écrit par un tiers avant de l'afficher. Le
    HTML n'est PAS retenu en repli — un fil de ticket qui accepterait du balisage
    venu d'un courriel ouvrirait une porte que `lint:html` ne surveille pas.
    """
    if message.is_multipart():
        for partie in message.walk():
            if partie.get_content_type() == "text/plain":
                charge = partie.get_payload(decode=True) or b""
                return charge.decode(partie.get_content_charset() or "utf-8", "replace")
        return ""
    if message.get_content_type() != "text/plain":
        return ""
    charge = message.get_payload(decode=True) or b""
    return charge.decode(message.get_content_charset() or "utf-8", "replace")


def _sans_citation(texte: str) -> str:
    """La réponse, sans le message cité en dessous.

    Une réponse par courriel recopie tout l'échange précédent. Le laisser
    entrerait dans le ticket une copie du ticket, à chaque échange, et le fil
    deviendrait illisible en trois messages.
    """
    lignes = []
    for ligne in texte.splitlines():
        nue = ligne.strip()
        if nue.startswith(">") or nue.startswith("-- "):
            break
        if nue.startswith("Le ") and nue.endswith("écrit :"):
            break
        lignes.append(ligne)
    return "\n".join(lignes).strip()[:MAX_CORPS]


def _ticket_de(session: Session, verdict) -> Ticket | None:
    """Le ticket visé, par le jeton d'abord. Aucun repli sur le sujet."""
    if verdict.jeton:
        return session.exec(
            select(Ticket).where(Ticket.jeton_courriel == verdict.jeton)
        ).first()
    return None


def _prevenir_le_cs(session: Session, ticket: Ticket | None, verdict) -> None:
    """Une notification par membre du conseil syndical — jamais un silence."""
    #  🔴 `membres_cs_ou_admin` et non `membres_cs_avec_email` : c'est une
    #  notification IN-APP. L'autre vise la boîte aux lettres et exige une
    #  adresse — ici elle priverait d'alerte un membre du CS qui n'en a pas.
    from app.utils.destinataires import membres_cs_ou_admin

    ou = f"le ticket #{ticket.numero}" if ticket else "un ticket"
    for membre in membres_cs_ou_admin(session):
        session.add(Notification(
            destinataire_id=membre.id,
            type="ticket_update",
            titre=f"Réponse par courriel non prise en compte sur {ou}",
            corps=(
                f"Un message de « {verdict.expediteur} » est arrivé en réponse à {ou}, "
                f"mais il n'a pas été ajouté au fil : {verdict.motif}. "
                "Le message reste consultable dans la boîte de réception."
            ),
            lien=f"/tickets/{ticket.id}" if ticket else "/tickets",
        ))


def traiter(session: Session, entetes: dict, corps: str, recu_le: datetime | None,
            plancher: datetime | None = None) -> str:
    """Applique le verdict d'UN message. Rend la décision prise, pour le journal.

    Séparée de la connexion IMAP pour être éprouvable : un test lui passe des
    en-têtes et vérifie ce qui est écrit en base, sans boîte aux lettres.
    """
    verdict = examiner(entetes, recu_le=recu_le, plancher=plancher)
    if verdict.decision == IGNORE:
        return IGNORE

    ticket = _ticket_de(session, verdict)
    if ticket is None:
        #  Rattaché en apparence (un jeton était présent) mais introuvable :
        #  ticket supprimé, ou jeton forgé. Rien à écrire, et personne de
        #  légitime à prévenir — prévenir ici ferait du bruit sur des tentatives.
        return IGNORE

    if verdict.decision == REFUSE:
        _prevenir_le_cs(session, ticket, verdict)
        session.commit()
        return REFUSE

    auteur = session.exec(
        select(Utilisateur).where(Utilisateur.email == verdict.expediteur.split("<")[-1]
                                  .strip(">").strip(), Utilisateur.actif == True)  # noqa: E712
    ).first()
    if auteur is None:
        #  Voir l'en-tête : pas de compte, pas d'écriture — mais on le DIT.
        _prevenir_le_cs(session, ticket, verdict.__class__(
            decision=REFUSE, jeton=verdict.jeton, reference=verdict.reference,
            expediteur=verdict.expediteur,
            motif="cet expéditeur, pourtant authentifié, n'a pas de compte sur le site",
        ))
        session.commit()
        return REFUSE

    texte = _sans_citation(corps)
    if not texte:
        return IGNORE

    session.add(TicketEvolution(
        ticket_id=ticket.id, type="commentaire", contenu=texte,
        auteur_id=auteur.id, cree_le=datetime.utcnow(),
    ))
    ticket.mis_a_jour_le = datetime.utcnow()
    session.add(ticket)
    session.commit()
    return ACCEPTE


def relever() -> dict[str, int]:
    """Relève la boîte et traite ce qui s'y trouve. Rend le compte par décision.

    ⚠️ N'échoue jamais bruyamment : elle tourne sous le planificateur, et une
    exception y tuerait le job pour de bon. Elle journalise, et rend un compte
    que le journal montre — un tuyau muet est un tuyau qu'on croit vivant.
    """
    from app.database import SessionLocal

    comptes = {ACCEPTE: 0, REFUSE: 0, IGNORE: 0}
    session = SessionLocal()
    try:
        cfg = config_imap(session)
        if (cfg.get("imap_enabled") or "").lower() not in ("1", "true", "oui"):
            return comptes

        plancher = PLANCHER_PAR_DEFAUT
        if cfg.get("imap_plancher"):
            try:
                plancher = datetime.fromisoformat(cfg["imap_plancher"])
            except ValueError:
                logger.warning("imap_plancher illisible (%s) — plancher par défaut",
                               cfg["imap_plancher"])

        boite = imaplib.IMAP4_SSL(cfg.get("imap_server", ""), int(cfg.get("imap_port") or 993))
        try:
            boite.login(cfg.get("imap_username", ""), cfg.get("imap_password", ""))
            boite.select(cfg.get("imap_dossier") or "INBOX")
            _statut, donnees = boite.search(None, "UNSEEN")
            for numero in (donnees[0].split() if donnees and donnees[0] else []):
                _st, brut = boite.fetch(numero, "(RFC822)")
                if not brut or not brut[0]:
                    continue
                message = email.message_from_bytes(brut[0][1])
                entetes = {cle: _texte(val) for cle, val in message.items()}
                try:
                    recu_le = parsedate_to_datetime(message.get("Date", "")).replace(tzinfo=None)
                except Exception:
                    recu_le = None
                decision = traiter(session, entetes, _corps_lisible(message), recu_le, plancher)
                comptes[decision] += 1
                boite.store(numero, "+FLAGS", "\\Seen")
        finally:
            try:
                boite.logout()
            except Exception:
                pass
    except Exception as exc:
        logger.error("Relève de la boîte des réponses : %s", exc)
    finally:
        session.close()

    if any(comptes.values()):
        logger.info("Réponses par courriel — écrites=%d refusées=%d ignorées=%d",
                    comptes[ACCEPTE], comptes[REFUSE], comptes[IGNORE])
    return comptes
