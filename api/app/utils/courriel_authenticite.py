"""L'expéditeur d'un courriel reçu est-il bien celui qu'il dit ? — vérifié ICI.

## 🔴 Pourquoi on ne lit plus `Authentication-Results` (28/09/2026)

#703 avait posé : *« `Authentication-Results` posé par le MTA fait foi — on ne
réimplémente ni SPF ni DKIM »*. Le raisonnement tenait **sur une hypothèse
fausse : que le serveur de réception écrive cet en-tête**. OVH ne l'écrit pas.

Ce que ça a coûté, constaté le 28/09/2026 dans les notifications du conseil :

- **aucune réponse par courriel n'est jamais entrée dans un fil** depuis la mise
  en service (05/09) — chaque message authentique était refusé pour « aucune
  trace de vérification d'authenticité » ;
- et, pire, **le contrôle croyait l'expéditeur** : un en-tête que personne ne
  pose à la réception, c'est l'expéditeur qui l'écrit. Un message forgé portant
  `Authentication-Results: x; spf=pass dkim=pass dmarc=pass` aurait été accepté.

## Ce qui fait foi désormais : une signature DKIM ALIGNÉE

On vérifie nous-mêmes la signature DKIM du message (`dkimpy`), et on exige que
le domaine signataire (`d=`) soit celui de l'adresse `From:` ou un domaine
parent — l'**alignement** qui fait passer DMARC. Sans lui, n'importe qui
signerait pour son propre domaine un message « de » quelqu'un d'autre.

Pourquoi DKIM et pas SPF : la boîte relevée reçoit par une **redirection**
(`affaire@` → `noreply@`). Le message y repart des serveurs d'OVH, et SPF — qui
juge l'adresse IP de l'émetteur — échoue alors par construction. La signature
DKIM, elle, voyage dans le message et survit à la redirection.

⚠️ **Ce que ça laisse dehors, et c'est voulu** : un domaine qui ne signe pas en
son nom. Son message est refusé, et le conseil est prévenu avec le motif — le
refus n'est jamais silencieux (`courriel_boite._prevenir_le_cs`).

## INCONNU n'est pas REFUSÉ

Un DNS injoignable ne dit rien de l'expéditeur. `VerificationReportee` laisse
le message **non lu** : la relève suivante le reprend. Le refuser ferait
notifier le conseil d'une usurpation qui n'en est pas une, et perdrait la
réponse pour de bon (`standards/04` — un contrôle qui ne peut pas s'exécuter
rend INCONNU, jamais un verdict).
"""

from __future__ import annotations

import logging
from email.utils import parseaddr

import dkim
import dns.exception
import dns.resolver

logger = logging.getLogger(__name__)


class _JournalDkim(logging.LoggerAdapter):
    """Le journal passé à `dkimpy`, qui écrit en ERROR une clé absente ou mal
    formée chez l'EXPÉDITEUR. Ce n'est pas une panne de l'API : le point 6 du
    pré-check compte les ERROR, et un courriel mal signé bloquerait une MEP. Le
    verdict, lui, n'est pas tu — il part au conseil avec son motif.
    """

    def error(self, msg, *args, **kwargs):
        self.debug(msg, *args, **kwargs)

    warning = error


_journal_dkim = _JournalDkim(logger, {})

#: Les algorithmes admis. `rsa-sha1` est déprécié (RFC 8301) : une signature
#: qui n'offre que lui ne prouve plus grand-chose.
_ALGORITHMES = (b"rsa-sha256", b"ed25519-sha256")

#: Délai d'une requête DNS, en secondes.
_DELAI_DNS = 5


class VerificationReportee(Exception):
    """La vérification n'a pas pu avoir lieu (DNS) — ni vrai ni faux : à reprendre."""


def _txt(nom: bytes, timeout: int = _DELAI_DNS) -> bytes | None:
    """La clé publique publiée dans le DNS, ou None si elle n'existe pas.

    Remplace le résolveur de `dkimpy`, qui confond « pas de clé » et « serveur
    DNS en panne » (`NoNameservers` → None) : la seconde doit REPORTER, pas
    refuser.
    """
    try:
        reponse = dns.resolver.resolve(
            nom.decode("ascii", "replace"), "TXT", raise_on_no_answer=False, lifetime=timeout
        )
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        return None
    except (dns.exception.Timeout, dns.resolver.NoNameservers) as exc:
        raise VerificationReportee(f"DNS injoignable ({type(exc).__name__})") from exc
    for enregistrement in reponse.response.answer:
        if enregistrement.rdtype == dns.rdatatype.TXT:
            return b"".join(list(enregistrement.items)[0].strings)
    return None


def domaine_de(adresse: str) -> str:
    """Le domaine d'une adresse d'en-tête (« Nom <a@b.fr> » → « b.fr »), minuscule."""
    return (parseaddr(adresse or "")[1] or "").rpartition("@")[2].strip().lower().rstrip(".")


def aligne(domaine_signataire: str, domaine_expediteur: str) -> bool:
    """Le signataire répond-il du domaine de l'expéditeur ?

    Le même domaine, ou un domaine PARENT (`d=exemple.fr` pour
    `From: …@mail.exemple.fr`) : qui publie les clés de `exemple.fr` en contrôle
    les sous-domaines. L'inverse n'est pas admis — un sous-domaine délégué ne
    répond pas de son parent —, et la comparaison se fait sur les LIBELLÉS : `d=
    exemple.fr` ne couvre pas `faux-exemple.fr`.
    """
    s, e = domaine_signataire.lower().rstrip("."), domaine_expediteur.lower().rstrip(".")
    if not s or not e or "." not in s:
        return False
    return e == s or e.endswith("." + s)


def verifier_expediteur(brut: bytes, from_: str, *, dnsfunc=_txt) -> tuple[bool, str]:
    """Rend `(vrai, motif)` : le message porte-t-il une signature DKIM valide et
    alignée sur son `From:` ?

    Le motif est écrit pour un membre du conseil syndical, qui le lira dans une
    notification — il dit ce qui manque, jamais « échec de la validation ».

    Lève `VerificationReportee` si le DNS ne répond pas : ce n'est pas un verdict.
    """
    expediteur = domaine_de(from_)
    if not expediteur:
        return False, "l'expéditeur du message est illisible"

    message = dkim.DKIM(brut, logger=_journal_dkim)
    nombre = sum(1 for nom, _ in message.headers if nom.lower() == b"dkim-signature")
    if not nombre:
        return False, (
            "le message ne porte aucune signature DKIM : il n'a pas pu être attribué "
            "avec certitude à son expéditeur apparent"
        )

    signataires: list[str] = []
    for idx in range(nombre):
        try:
            valide = message.verify(idx=idx, dnsfunc=dnsfunc)
        except VerificationReportee:
            raise
        except Exception:  # noqa: BLE001 — une signature mal formée ne vaut rien
            continue
        champs = getattr(message, "signature_fields", {}) or {}
        signataire = (champs.get(b"d") or b"").decode("ascii", "replace").lower()
        if not valide:
            continue
        #  `l=` borne la longueur du corps signé : ce qui suit peut être AJOUTÉ
        #  sans casser la signature. Une réponse dont la fin est libre ne prouve
        #  rien de ce qu'elle dit.
        if b"l" in champs or champs.get(b"a") not in _ALGORITHMES:
            continue
        #  RFC 6376 impose de signer `From` ; on ne s'en remet pas au signataire.
        if b"from" not in getattr(message, "include_headers", ()):
            continue
        signataires.append(signataire)
        if aligne(signataire, expediteur):
            return True, f"signé par {signataire}"

    if signataires:
        return False, (
            f"le message est signé par {', '.join(sorted(set(signataires)))}, "
            f"et non par le domaine de l'expéditeur ({expediteur})"
        )
    return False, "la signature DKIM du message est invalide"
