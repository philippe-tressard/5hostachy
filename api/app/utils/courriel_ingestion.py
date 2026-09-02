"""Ce qu'on fait d'un message arrivé dans la boîte des réponses (#703).

## La décision est ICI, et elle est PURE

Ce module ne se connecte à rien. Il reçoit les en-têtes et le corps d'un message
déjà lu, et rend un **verdict**. La relève IMAP vit dans `courriel_boite.py`, et
l'écriture dans le ticket dans le routeur.

C'est la leçon la plus chère de ce dépôt : *« je testais la décision, pas le
tuyau qui la nourrit »*. Ici on peut faire l'inverse — éprouver chaque verdict
sur un message écrit à la main, y compris les messages hostiles, sans boîte et
sans réseau.

## 🔴 SMTP N'AUTHENTIFIE PAS L'EXPÉDITEUR

C'est le seul point qui compte vraiment. N'importe qui peut écrire à cette boîte
en mettant l'adresse du syndic dans le `From:`. Sans vérification, son message
deviendrait un **commentaire officiel sur un ticket, visible des résidents, signé
du syndic**.

Notre DMARC en `p=reject` protège *notre* domaine contre l'usurpation — **pas
celui du syndic**. La preuve doit donc être cherchée là où elle est produite : les
en-têtes `Authentication-Results` que le serveur de réception a posés en
constatant SPF, DKIM et DMARC. Un message qui n'en porte pas n'est pas « probablement
bon » : il est **invérifiable**, et invérifiable n'est jamais OK
(`standards/04`).

## Que fait-on d'un message qui ne passe pas ?

Trois options existaient. La retenue est la deuxième :

| Option | Conséquence |
|---|---|
| rejeter en silence | sûr, mais une réponse légitime disparaît sans que personne ne le sache — « un contrôle sans destinataire » |
| **rejeter ET prévenir le conseil syndical** | sûr *et* visible : rien n'est écrit dans le ticket, mais quelqu'un sait qu'un message attend |
| accepter en marquant « non vérifié » | ❌ écartée : un badge ne protège personne, on le lit une fois et plus jamais |

**Le silence est ce qui rend un filtre dangereux.** Un filtre qu'on n'entend
jamais finit par être cru parfait, et il l'est d'autant moins que personne ne le
regarde.

## La date plancher

*« À automatiser à partir des mails reçus au 2 septembre 2026 »* (arbitrage du
02/09/2026). Sans elle, la première relève rejouerait des mois d'archives et
déverserait dans les tickets des réponses déjà traitées à la main. Elle est
**configurable**, mais elle a une valeur : `PLANCHER_PAR_DEFAUT`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parseaddr

from app.utils.courriel_entrant import jeton_dans

#: Les messages antérieurs sont ignorés — arbitrage du 02/09/2026.
PLANCHER_PAR_DEFAUT = datetime(2026, 9, 2)

#: Verdicts possibles. Ils sont trois et pas deux : « je ne sais pas rattacher »
#: n'est pas « je refuse », et les confondre ferait notifier le conseil syndical
#: pour chaque prospectus arrivé dans la boîte.
ACCEPTE = "accepte"          # à écrire dans le ticket
REFUSE = "refuse"            # rattaché, mais non authentifié → prévenir le CS
IGNORE = "ignore"            # sans rapport avec un ticket → ne rien faire


@dataclass(frozen=True)
class Verdict:
    """Ce qu'on fait du message, et pourquoi — le motif est destiné à un humain."""

    decision: str
    jeton: str | None = None
    reference: str | None = None
    expediteur: str = ""
    motif: str = ""


#: Un `Authentication-Results` qui CONSTATE un succès. On exige les trois
#: mécanismes séparément plutôt qu'un `dmarc=pass` seul : un DMARC en `p=none`
#: sur un domaine mal configuré peut passer sans qu'aucune signature ne tienne.
_SPF = re.compile(r"\bspf=pass\b", re.IGNORECASE)
_DKIM = re.compile(r"\bdkim=pass\b", re.IGNORECASE)
_DMARC = re.compile(r"\bdmarc=pass\b", re.IGNORECASE)

#: Les `Message-ID` cités par une réponse, dans l'ordre où on les préfère.
_REFERENCE = re.compile(r"<([^<>@\s]+@[^<>\s]+)>")


def expediteur_authentifie(authentication_results: str | None, from_: str) -> tuple[bool, str]:
    """Le serveur de réception a-t-il CONSTATÉ l'authenticité de l'expéditeur ?

    Rend `(vrai, motif)`. Le motif est écrit pour être lu par un membre du
    conseil syndical dans une notification, pas par un administrateur système :
    il dit ce qui manque, jamais « échec de la validation ».

    ⚠️ Trois conditions, et l'absence d'en-tête en est une. Un message sans
    `Authentication-Results` n'a pas échoué : **il n'a pas été vérifié**, ce qui
    est pire, parce que rien ne le distingue d'un message forgé.
    """
    if not authentication_results:
        return False, (
            "aucune trace de vérification d'authenticité : ce message n'a pas pu "
            "être attribué avec certitude à son expéditeur apparent"
        )
    manquants = [
        nom
        for nom, motif in (("SPF", _SPF), ("DKIM", _DKIM), ("DMARC", _DMARC))
        if not motif.search(authentication_results)
    ]
    if manquants:
        return False, (
            "l'expéditeur n'est pas authentifié — contrôle(s) non passé(s) : "
            + ", ".join(manquants)
        )
    domaine_from = (parseaddr(from_)[1] or "").rsplit("@", 1)[-1].lower()
    if not domaine_from:
        return False, "l'expéditeur du message est illisible"
    return True, f"authentifié pour {domaine_from}"


def reference_citee(in_reply_to: str | None, references: str | None) -> str | None:
    """Le `Message-ID` auquel cette réponse répond, s'il est cité.

    Seconde voie de rattachement, employée quand le jeton n'est pas dans
    l'adresse — un serveur qui refuserait le sous-adressage, un client qui aurait
    réécrit le destinataire. `In-Reply-To` d'abord : `References` porte toute la
    chaîne, et le dernier n'est pas toujours le bon.
    """
    for valeur in (in_reply_to, references):
        if not valeur:
            continue
        trouves = _REFERENCE.findall(valeur)
        if trouves:
            return trouves[-1].lower()
    return None


def examiner(
    entetes: dict[str, str],
    *,
    recu_le: datetime | None = None,
    plancher: datetime | None = None,
) -> Verdict:
    """Le verdict, à partir des seuls en-têtes. Aucun accès réseau ni base.

    L'ordre des tests n'est pas indifférent :

    1. **la date** — avant tout, sinon la première relève traiterait l'archive ;
    2. **le rattachement** — sans ticket, il n'y a personne à prévenir, et un
       message sans rapport ne doit produire aucun bruit ;
    3. **l'authentification** — en dernier, parce que c'est le seul cas où l'on
       veut *parler*. L'inverser ferait notifier le conseil syndical pour chaque
       message non authentifié de la boîte, ticket ou pas : le filtre deviendrait
       lui-même la nuisance, et on finirait par ne plus le lire.
    """
    lire = {k.lower(): v for k, v in entetes.items()}
    plancher = plancher or PLANCHER_PAR_DEFAUT
    from_ = lire.get("from", "")

    if recu_le is not None and recu_le < plancher:
        return Verdict(IGNORE, expediteur=from_, motif="antérieur à la date de mise en service")

    jeton = jeton_dans(
        lire.get("to"), lire.get("delivered-to"), lire.get("envelope-to"), lire.get("cc")
    )
    reference = reference_citee(lire.get("in-reply-to"), lire.get("references"))
    if not jeton and not reference:
        return Verdict(IGNORE, expediteur=from_, motif="ne répond à aucun ticket")

    ok, motif = expediteur_authentifie(lire.get("authentication-results"), from_)
    if not ok:
        return Verdict(REFUSE, jeton=jeton, reference=reference, expediteur=from_, motif=motif)
    return Verdict(ACCEPTE, jeton=jeton, reference=reference, expediteur=from_, motif=motif)
