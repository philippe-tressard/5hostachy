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

import logging
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Request

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
async def recevoir_rapport(request: Request):
    """Reçoit un rapport de violation. **Ne rend rien** — 204, toujours.

    Un rapport illisible n'est pas une erreur du client : c'est un format qu'on ne
    connaît pas encore. On le compte à part plutôt que de répondre 4xx, qui ferait
    réessayer le navigateur en boucle.
    """
    global _recus, _ignores
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
    if not retenir(extrait):
        _ignores += 1


@router.get("/admin/csp-violations")
def lire_violations(_admin: Utilisateur = Depends(require_admin)) -> dict[str, Any]:
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
