"""Router publications — actualités du fil, leur suivi et leurs envois.

`publications.py` faisait **682 lignes**. Découpé le 11/08/2026, au fil de l'eau :
l'ajout du renvoi WhatsApp l'avait fait passer de 653 à 682, et c'est le
garde-fou de modularité (`scripts-ci-modularite.sh`) qui a refusé le lot. Le
contrôle a fonctionné comme prévu — on découpe le fichier quand on y touche.

## La règle de découpage : un domaine, un module

Reprise de `app/routers/tickets/`, `admin/` et `flux/` — par domaine, chacun
ayant sa propre raison de changer.

| Module | Ce qui y change |
|---|---|
| `crud` | cycle de vie : lister, créer, modifier, supprimer, renvoyer |
| `evolutions` | fil de suivi : changements d'état et commentaires |
| `courriels` | composition et envoi des courriels d'une publication |
| `commun` | sérialisation, archivage, annonce de hall |

## Ce qui a été factorisé au passage

`EvolutionRead` était construit **trois fois** — dans `_pub_to_read`,
`update_evolution` et `add_evolution` —, avec chaque fois la même résolution de
l'auteur et le même `json.loads` défensif sur `fichiers_urls`. Trois copies
d'une sérialisation de dix champs divergent au premier champ ajouté : il
n'aurait été mis à jour qu'à deux endroits sur trois, sans que rien ne le
signale. → `commun.evolution_read`.

## Ordre de montage

`evolutions` est monté avant `crud`, comme dans `tickets/` : ses chemins sont
plus spécifiques (`/{pub_id}/evolutions`) que le `/{pub_id}` de `crud`, et
FastAPI résout dans l'ordre d'enregistrement. Les 8 chemins sont identiques au
caractère près à ceux d'avant le découpage.
"""
from fastapi import APIRouter

from . import crud, evolutions

#  Le sous-module à chemins nus reçoit le préfixe ici. Ce littéral est aussi ce
#  que lit `test_endpoints_orphelins` pour reconstruire les chemins d'un paquet
#  découpé : le garder en clair n'est pas cosmétique.
_a_prefixer = APIRouter(prefix="/publications", tags=["publications"])
_a_prefixer.include_router(evolutions.router)

router = APIRouter(tags=["publications"])
router.include_router(_a_prefixer)
router.include_router(crud.router)

#  Surface publique conservée pour les importateurs externes : `flux/publications`
#  décide de l'archivage avec EXACTEMENT la même règle que /actualités — les deux
#  vues doivent trancher pareil, sinon un élément apparaît dans l'une et pas dans
#  l'autre (bug du 17/07/2026). Le découpage ne doit pas rouvrir cette porte.
from .commun import (  # noqa: E402  (après le montage, pour la lisibilité)
    ARCHIVAGE_DELAI_HEURES,
    PUBLIE_VISIBILITE_JOURS,
    STATUT_LABELS,
    STATUTS_PUBLICATION,
    _is_archived,
)

__all__ = [
    "router",
    "ARCHIVAGE_DELAI_HEURES",
    "PUBLIE_VISIBILITE_JOURS",
    "STATUT_LABELS",
    "STATUTS_PUBLICATION",
    "_is_archived",
]
