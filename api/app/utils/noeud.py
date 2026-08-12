"""Sur quel nœud cette API s'exécute-t-elle ?

Remonté ici depuis `routers/admin/exploitation.py` le 12/08/2026 (#312) : la
fonction y était privée, alors que ses appelants sont désormais des deux côtés
— des routers (déclenchements manuels) **et** des jobs de `utils/` (sauvegarde
automatique, agrégation de la télémétrie). L'importer depuis un router dans un
job aurait inversé la dépendance ; la recopier en aurait fait un second
mécanisme d'identification du nœud, ce que #312 interdit explicitement.
"""
from typing import Optional

from app.config import get_settings


def noeud_courant() -> Optional[str]:
    """Nœud sur lequel cette API s'exécute, ou `None` hors production.

    `INSTANCE_ID` est déjà injecté dans le conteneur par docker-compose et sert
    au front pour afficher « RPi1 » au pied de page. On le réutilise plutôt que
    d'inventer une seconde source.

    ⚠️ **Cette valeur ne vaut qu'au moment où l'on ÉCRIT une ligne.** Elle
    nomme le nœud qui exécute, ce qui est juste pour une tâche en train de
    tourner — et faux pour une ligne déjà enregistrée. Jusqu'au 11/08/2026, la
    santé des tâches l'affichait à la **lecture** : le rôle alternant chaque
    nuit, une sauvegarde faite par rpi1 se présentait comme « rpi2 » dès la
    bascule suivante. La colonne d'une ligne historique se lit en base, jamais
    ici (`standards/04` : ne jamais présenter une valeur par défaut comme une
    mesure).
    """
    identifiant = (get_settings().instance_id or "").strip()
    return f"rpi{identifiant}" if identifiant else None
