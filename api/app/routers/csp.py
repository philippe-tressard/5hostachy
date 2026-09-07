"""Collecte des violations de Content-Security-Policy — pour MESURER avant de bloquer.

## Pourquoi (#536)

`script-src` et `style-src` apportent l'essentiel de la protection contre le XSS,
et **rendent une application SvelteKit blanche** si on les pose sans mesurer :
styles en ligne du compilateur, script d'hydratation, polices. Un remède posé sans
pouvoir l'observer serait pire que le mal.

Le geste prescrit est donc `Content-Security-Policy-Report-Only` : le navigateur
**signale sans bloquer**. Reste à savoir où il signale — et le site n'est
accessible que derrière une connexion, ce qui interdit d'aller lire la console de
quelqu'un d'autre. D'où ce point de collecte.

## Ce qui est délibéré, et pourquoi

**Aucune table, aucune migration.** Les violations sont agrégées **en mémoire**,
par `(directive, origine bloquée)`. C'est suffisant pour la seule question posée —
*quelles directives faudra-t-il assouplir ?* — et cela évite d'ouvrir une écriture
en base à un endpoint **non authentifié**. Le compte repart à zéro au
redémarrage : c'est assumé, la mesure dure quelques jours.

**L'endpoint est public**, et il doit l'être : le navigateur poste le rapport sans
cookie ni en-tête d'authentification. Trois bornes en découlent :

  • une limite de débit (comme `/auth/*`) ;
  • un plafond de clés distinctes, pour qu'un envoi forgé ne fasse pas gonfler la
    mémoire indéfiniment ;
  • aucune donnée du rapport n'est renvoyée à l'appelant.

⚠️ Le contenu d'un rapport vient du **navigateur**, donc d'une source non fiable.
Il n'est jamais interprété : ni évalué, ni rendu en HTML, ni écrit en base. Il est
tronqué, compté, et lu par un administrateur.
"""

import json
import logging
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.database import get_session

from app.auth.deps import require_admin
from app.models.core import Utilisateur
from app.utils.limiter import limiter

logger = logging.getLogger("hostachy.csp")

router = APIRouter(tags=["csp"])

#  Plafond de clés distinctes retenues. Au-delà, on cesse d'en ajouter : un
#  rapport forgé ne doit pas faire croître la mémoire sans fin. Le compte des
#  rapports reçus, lui, continue — c'est ce qui rend le débordement VISIBLE au
#  lieu de le taire.
PLAFOND_CLES = 200

#  Longueur retenue d'une origine bloquée. Une URL vient du navigateur : on la
#  tronque avant de s'en servir comme clé.
LONGUEUR_MAX = 200

_violations: Counter = Counter()
_recus = 0
_ignores = 0

#  ── PERSISTANCE ──────────────────────────────────────────────────────────────
#
#  🔴 Sans elle, ce point de collecte ne collecte RIEN sur un site en cours de
#  développement. Le relevé vivait en mémoire de processus, et chaque
#  déploiement recrée le conteneur : le 29/08/2026, SIX déploiements ont eu lieu
#  dans la journée, et la fenêtre d'observation n'a jamais dépassé quelques
#  dizaines de minutes. Constaté sur la production — `docker logs` : 0 ligne CSP,
#  conteneur « Up About a minute ».
#
#  ⚠️ C'est un faux vert de la famille la plus traître : le relevé rendait
#  « aucune violation », ce qui se lit « le site est conforme ». Le code avait
#  bien prévu le TÉMOIN pour `recus == 0`… mais pas le cas où des rapports sont
#  arrivés et ont été effacés. `standards/04` §2 — un contrôle doit dire quand il
#  n'a pas pu mesurer, et « effacé au dernier déploiement » en fait partie.
#
#  ⚠️ On écrit dans `config_site`, la table clé/valeur déjà employée pour les
#  marqueurs de semis — pas de migration, et la donnée voyage avec la base lors
#  d'une bascule. C'est une écriture IN-PROCESS : la règle d'or sur `app.db` est
#  respectée (`standards/06` §1).
CLE_PERSISTANCE = "csp_violations"

#  Une écriture toutes les N conservations, EN PLUS de chaque clé nouvelle. Le
#  point est PUBLIC : écrire à chaque rapport donnerait 60 écritures/minute au
#  plafond de débit. Les clés nouvelles sont bornées par `PLAFOND_CLES` (200
#  écritures au total, quoi qu'il arrive) ; le diviseur borne le reste.
PERSISTER_TOUS_LES = 25

_charge = False


def _etat() -> dict:
    return {
        "recus": _recus,
        "ignores": _ignores,
        "violations": [[d, b, n] for (d, b), n in _violations.items()],
    }


def doit_persister(nouvelle: bool, recus: int) -> bool:
    """Faut-il écrire le relevé maintenant ?

    Une BORNE, donc une fonction pure et testée seule — le motif du dépôt pour
    les décisions d'infra. Elle ne peut pas se vérifier par HTTP : le client de
    test fait tourner l'application dans un autre fil, donc sur une autre base
    en mémoire (`SingletonThreadPool`), et l'écriture y disparaît. Éprouver la
    décision ici, l'écriture par `_persister`, chacune pour ce qu'elle est.

    ⚠️ Une clé NOUVELLE s'écrit tout de suite : c'est ce qu'on vient chercher.
    Une répétition n'apprend rien et attend le diviseur — le point est PUBLIC,
    et écrire à chaque rapport donnerait soixante écritures par minute au
    plafond de débit.
    """
    return nouvelle or recus % PERSISTER_TOUS_LES == 0


def _persister(session) -> None:
    """Écrit le relevé dans `config_site`. Silencieux en cas d'échec — un point
    de collecte ne doit jamais faire échouer la page qui l'appelle."""
    from app.models.core import ConfigSite

    try:
        ligne = session.get(ConfigSite, CLE_PERSISTANCE)
        valeur = json.dumps(_etat(), ensure_ascii=False)
        if ligne:
            ligne.valeur = valeur
        else:
            ligne = ConfigSite(cle=CLE_PERSISTANCE, valeur=valeur)
        session.add(ligne)
        session.commit()
    except Exception:  # pragma: no cover - défense, jamais atteinte en essai
        logger.warning("CSP — relevé non persisté", exc_info=True)


def charger(session) -> None:
    """Restaure le relevé du dernier redémarrage. Idempotent.

    ⚠️ Appelée à la PREMIÈRE utilisation et non au démarrage : le module est
    importé avant que la base soit prête, et un chargement en tête ferait échouer
    le démarrage du conteneur — `start.sh` a `set -e`.
    """
    global _recus, _ignores, _charge
    if _charge:
        return
    _charge = True
    from app.models.core import ConfigSite

    try:
        ligne = session.get(ConfigSite, CLE_PERSISTANCE)
        if not ligne:
            return
        etat = json.loads(ligne.valeur)
        _recus = int(etat.get("recus", 0))
        _ignores = int(etat.get("ignores", 0))
        for d, bloque, n in etat.get("violations", []):
            _violations[(d, bloque)] = int(n)
    except Exception:  # pragma: no cover - une valeur illisible ne bloque rien
        logger.warning("CSP — relevé illisible, on repart de zéro", exc_info=True)


def _extraire(rapport: dict[str, Any]) -> tuple[str, str] | None:
    """La directive et l'origine bloquée, quel que soit le format du navigateur.

    ⚠️ Il y en a DEUX, et ils coexistent selon les navigateurs : l'ancien
    `{"csp-report": {...}}` (report-uri) et le nouveau `{"body": {...}}`
    (Reporting API). Ne lire que l'un des deux donnerait un relevé vide sur la
    moitié du parc — et un relevé vide, ici, se lit « aucune violation ».
    """
    corps = rapport.get("csp-report") or rapport.get("body") or rapport
    if not isinstance(corps, dict):
        return None
    directive = corps.get("effective-directive") or corps.get("effectiveDirective") or corps.get("violated-directive")
    bloque = corps.get("blocked-uri") or corps.get("blockedURL") or corps.get("blocked-url")
    if not directive:
        return None
    return (str(directive)[:80], str(bloque or "—")[:LONGUEUR_MAX])


def retenir(cle: tuple[str, str]) -> bool:
    """Compte une violation, ou refuse si le plafond de clés est atteint.

    Séparée de l'endpoint parce que c'est une BORNE, et qu'une borne s'éprouve
    seule : la tester par HTTP la ferait passer derrière la limite de débit, qui
    couperait avant qu'on l'atteigne. Deux bornes distinctes, deux tests
    distincts — et surtout, pas de test qui recopierait cette décision pour la
    vérifier contre elle-même.
    """
    if cle not in _violations and len(_violations) >= PLAFOND_CLES:
        return False
    _violations[cle] += 1
    #  Journalisé au premier passage seulement : une page qui viole une directive
    #  la viole à chaque chargement, et le journal serait noyé.
    if _violations[cle] == 1:
        logger.warning("CSP — nouvelle violation : %s ← %s", cle[0], cle[1])
    return True


@router.post("/csp-report", status_code=204)
@limiter.limit("60/minute")
async def recevoir_rapport(request: Request, session: Session = Depends(get_session)):
    """Reçoit un rapport de violation. **Ne rend rien** — 204, toujours.

    Un rapport illisible n'est pas une erreur du client : c'est un format qu'on ne
    connaît pas encore. On le compte à part plutôt que de répondre 4xx, qui ferait
    réessayer le navigateur en boucle.
    """
    global _recus, _ignores
    charger(session)
    _recus += 1
    try:
        rapport = await request.json()
    except Exception:
        _ignores += 1
        return
    extrait = _extraire(rapport) if isinstance(rapport, dict) else None
    if extrait is None:
        _ignores += 1
        return
    nouvelle = extrait not in _violations
    if not retenir(extrait):
        _ignores += 1
        return
    #  Une clé NOUVELLE est ce qu'on vient chercher : elle se persiste tout de
    #  suite. Les répétitions attendent le diviseur — elles n'apprennent rien.
    if doit_persister(nouvelle, _recus):
        _persister(session)


@router.get("/admin/csp-violations")
def lire_violations(
    session: Session = Depends(get_session),
    _admin: Utilisateur = Depends(require_admin),
) -> dict[str, Any]:
    """Le relevé agrégé, du plus fréquent au moins fréquent.

    ⚠️ `ignores` n'est pas du bruit : un chiffre élevé veut dire que des rapports
    arrivent dans un format qu'on ne sait pas lire, ou que le plafond de clés est
    atteint — dans les deux cas, le relevé est INCOMPLET et le dire évite de
    conclure « il n'y a plus rien à corriger ».
    """
    #  🔴 LE TÉMOIN (standards/04 §27). Un relevé vide ne veut PAS dire « le site
    #  est conforme » : il veut peut-être dire que l'en-tête `Report-Only` n'est
    #  pas servi, et qu'aucun navigateur n'a rien à signaler à personne.
    #
    #  On attend des violations, et c'est le but : SvelteKit insère un script
    #  d'hydratation EN LIGNE, que `script-src 'self'` refuse. Zéro rapport après
    #  quelques visites est donc SUSPECT, pas rassurant — et le contrôle C23 ne
    #  peut pas le dire à notre place : exiger un en-tête temporaire recréerait le
    #  faux positif qui a fait retirer `check-stack.sh` du cron (#301).
    charger(session)
    note = (
        "aucun rapport reçu — vérifier que l'en-tête Content-Security-Policy-Report-Only "
        "est bien servi (curl -sI) AVANT de conclure que le site est conforme"
        if _recus == 0
        else None
    )
    return {
        "note": note,
        "recus": _recus,
        "ignores": _ignores,
        "cles_distinctes": len(_violations),
        "plafond_atteint": len(_violations) >= PLAFOND_CLES,
        "violations": [
            {"directive": d, "bloque": b, "compte": n}
            for (d, b), n in _violations.most_common(100)
        ],
    }
