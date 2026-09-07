"""Router sondages — création, vote, résultats.

`sondages.py` faisait **514 lignes**. Découpé le 17/08/2026, au fil de l'eau :
le correctif de #397 (les résultats ne quittent le serveur que s'ils sont
lisibles) l'a fait passer de 496 à 514, et c'est le garde-fou de modularité
(`scripts-ci-modularite.sh`) qui a refusé le lot. Le contrôle a fonctionné comme
prévu — on découpe le fichier quand on y touche.

## La règle de découpage : un domaine, un module

Reprise de `app/routers/publications/`, `tickets/`, `admin/` et `flux/` — par
domaine, chacun ayant sa propre raison de changer.

| Module | Ce qui y change |
|---|---|
| `crud` | cycle de vie : lister, consulter, créer, modifier, supprimer, clôturer |
| `participation` | ce que font les résidents : voter, commenter |
| `commun` | schémas partagés et la garde d'accès à la rubrique Communauté |

## Ordre de montage

`participation` est monté avant `crud`, comme dans `publications/` et
`tickets/` : ses chemins sont plus spécifiques (`/{sondage_id}/voter`) que le
`/{sondage_id}` de `crud`, et FastAPI résout dans l'ordre d'enregistrement. Les
9 chemins sont identiques au caractère près à ceux d'avant le découpage —
`tests/test_endpoints_orphelins.py` les vérifie.
"""
from fastapi import APIRouter

from . import crud, participation

#  Le sous-module à chemins nus reçoit le préfixe ici. Ce littéral est aussi ce
#  que lit `test_endpoints_orphelins` pour reconstruire les chemins d'un paquet
#  découpé : le garder en clair n'est pas cosmétique.
_a_prefixer = APIRouter(prefix="/sondages", tags=["sondages"])
_a_prefixer.include_router(participation.router)

router = APIRouter(tags=["sondages"])
router.include_router(_a_prefixer)
router.include_router(crud.router)

#  Surface publique conservée pour les importateurs externes : `flux/` compose le
#  fil d'activité à partir des sondages et lit ces schémas. Le découpage ne doit
#  pas casser un import existant.
from .commun import (  # noqa: E402  (après le montage, pour la lisibilité)
    OptionCreate,
    OptionRead,
    SondageCreate,
    SondageDetail,
    SondageRead,
)

__all__ = [
    "router",
    "OptionCreate",
    "OptionRead",
    "SondageCreate",
    "SondageDetail",
    "SondageRead",
]
