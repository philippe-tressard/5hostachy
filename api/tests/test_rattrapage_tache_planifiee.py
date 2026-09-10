"""Rattraper une tâche de 02:00 que le redémarrage a fait sauter (#876).

## L'incident (10/09/2026)

| Heure | Fait |
|---|---|
| 01:58:01 | `auto-deploy.sh` écrit `Déployé: c5d61a8` |
| **02:00:00** | créneau du job `telemetry_aggregation` |
| 02:00:08 | le conteneur démarre |
| 02:00:13 | `Scheduler started`, puis `Added job` |

Treize secondes. APScheduler tient ses jobs en **mémoire** : un créneau franchi
pendant un arrêt n'est pas rejoué, et le suivant se calcule à partir de l'instant
d'ajout. L'agrégation du 10 septembre n'a pas eu lieu.

🔴 **Ce n'était pas un hasard.** `auto-deploy.sh` tourne toutes les cinq minutes,
et `bascule.sh` redémarre la pile à **02:00 précises** en cron root — la même
minute que ce job. La collision est structurelle ; cette nuit-là, c'est la mise
en production qui a gagné la course.

## Pourquoi la règle interroge le FAIT

`misfire_grace_time` couvre un retard **du processus vivant**, pas un arrêt :
sans jobstore persistant, il n'y a rien à rattraper au démarrage. La question
posée est donc *quand la dernière agrégation a-t-elle réussi ?* — et la même
réponse couvre toutes les causes d'arrêt : mise en production, bascule, coupure
de courant, panne.

⚠️ Fonction **pure**, testée sans base ni planificateur. Une règle de rattrapage
qui aurait besoin d'un redémarrage pour être vérifiée ne serait vérifiée qu'en
production, c'est-à-dire trop tard — c'est exactement ce que cet incident a
coûté.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.utils.telemetry_aggregation import rattrapage_necessaire

MAINTENANT = datetime(2026, 9, 10, 8, 0)


def test_aucune_trace_DECLENCHE_le_rattrapage():
    """Base neuve ou tâche jamais passée : les deux méritent une première
    exécution, et elle est inoffensive."""
    assert rattrapage_necessaire(None, MAINTENANT) is True


def test_un_passage_RECENT_ne_declenche_rien():
    """Le cas nominal — un redémarrage à 14 h ne relance pas l'agrégation."""
    assert rattrapage_necessaire(MAINTENANT - timedelta(hours=2), MAINTENANT) is False


def test_un_passage_MANQUE_declenche():
    """Trente heures sans agrégation : le créneau de 02:00 a sauté."""
    assert rattrapage_necessaire(MAINTENANT - timedelta(hours=30), MAINTENANT) is True


def test_le_bord_des_24_heures():
    """🔴 Le bord exact, parce que c'est lui qui décide chaque matin.

    À 23 h 59, le passage de cette nuit a eu lieu — ne rien faire. À 24 h 01, il
    a été manqué. Un `>=` au lieu d'un `>` relancerait l'agrégation à chaque
    redémarrage tombant pile 24 h après la précédente, ce qui est fréquent
    puisque la tâche est **quotidienne**.
    """
    assert rattrapage_necessaire(MAINTENANT - timedelta(hours=23, minutes=59), MAINTENANT) is False
    assert rattrapage_necessaire(MAINTENANT - timedelta(hours=24), MAINTENANT) is False
    assert rattrapage_necessaire(MAINTENANT - timedelta(hours=24, minutes=1), MAINTENANT) is True


@pytest.mark.parametrize("heures", [1, 6, 12, 23])
def test_aucun_rattrapage_dans_la_journee(heures):
    """Plusieurs déploiements dans la même journée ne rejouent pas la tâche.

    C'est le cas réel du 09/09/2026 : cinq mises en production en une nuit. Sans
    ce bord, chacune aurait relancé une agrégation complète.
    """
    assert rattrapage_necessaire(MAINTENANT - timedelta(hours=heures), MAINTENANT) is False


def test_la_periode_est_un_PARAMETRE():
    """La règle vaut pour les autres tâches `cron` — sauvegarde à 03:00, contrôle
    de santé à 06:00 —, qui sont exposées au même trou. Elle ne code donc pas
    « 24 » en dur."""
    assert rattrapage_necessaire(MAINTENANT - timedelta(hours=8), MAINTENANT, periode_h=6) is True
    assert rattrapage_necessaire(MAINTENANT - timedelta(hours=8), MAINTENANT, periode_h=12) is False
