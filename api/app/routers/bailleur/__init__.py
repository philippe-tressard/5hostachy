"""Router bailleur — le bail locatif, son inventaire et les accès qui le suivent.

`bailleur.py` faisait **829 lignes**. Découpé le 06/09/2026, au fil de l'eau :
livrer l'ajout d'un objet à l'inventaire (#806) l'avait fait passer de 813 à 829,
et c'est le garde-fou de modularité qui a refusé le lot. Le contrôle a fonctionné
comme prévu — on découpe le fichier **quand on y touche**.

⚠️ Et il n'y avait pas d'autre issue : raboter les commentaires pour repasser
sous le seuil est explicitement interdit (`standards/02` §6). Les trois réponses
possibles sont « découper », « remonter la règle d'un cran », ou rien.

## La règle de découpage : un domaine, un module

Reprise de `routers/publications/`, `routers/tickets/` et `routers/admin/` —
chaque module a sa propre raison de changer.

| Module | Ce qui y change | Lignes |
|---|---|---|
| `baux` | cycle de vie du bail, et la recherche du locataire à y rattacher | 294 |
| `objets` | l'inventaire : remise, correction, retour, suppression | 130 |
| `acces` | transfert et récupération des badges, vue du locataire | 347 |
| `commun` | l'autorisation d'accès à un bail, et les schémas partagés | 154 |

## 🔴 Ce que le découpage a mis en commun, et pourquoi c'était le point sensible

`_get_bail_or_404` porte la **règle d'autorisation** du domaine : *ce bail est le
vôtre, ou vous êtes admin/CS*. Elle est désormais dans `commun`, importée par les
trois autres — jamais recopiée.

C'est la leçon de `_require_bailleur`, doublon exact de `require_proprietaire`
posé hors du module central, avec 17 endpoints dessus : **une règle
d'autorisation écrite deux fois se durcit une fois sur deux**. Un découpage est
exactement le moment où l'on est tenté de la recopier « pour éviter un import ».

## Ordre de montage

`objets` et `acces` sont montés **avant** `baux`, comme dans `tickets/` et
`publications/` : leurs chemins sont plus spécifiques
(`/baux/{id}/objets`, `/baux/{id}/acces`) que le `/baux/{bail_id}` de `baux`, et
FastAPI résout dans l'ordre d'enregistrement.

⚠️ Les 19 chemins sont identiques **au caractère près** à ceux d'avant le
découpage : le préfixe `/bailleur` est posé ici, une seule fois, et
`api/tests/test_endpoints_orphelins.py` le vérifie en même temps qu'il vérifie
que chacun a un consommateur.
"""
from fastapi import APIRouter

from . import acces, baux, objets

router = APIRouter(prefix="/bailleur", tags=["bailleur"])

#  L'ordre compte : du plus spécifique au plus général (voir l'en-tête).
router.include_router(objets.router)
router.include_router(acces.router)
router.include_router(baux.router)
