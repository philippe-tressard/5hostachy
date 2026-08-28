"""Router flux — agrégation temps réel pour le tableau de bord « pouls ».

`flux.py` faisait **1044 lignes**, dont un unique endpoint de 780 lignes portant
douze rubriques numérotées à la file. C'est le fichier d'API le plus modifié du
dépôt — 19 commits en 60 jours — et c'est celui que j'ai fait grossir de 996 à
1044 lignes le 07/08/2026 alors que la règle des 500 lignes existait déjà.
Découpé le 08/08/2026 ; le garde-fou `scripts-ci-modularite.sh`, écrit le même
jour, existe précisément pour que cette dérogation ne se répète pas.

## La règle de découpage : une rubrique, un module

Reprise de `app/routers/admin/` (06/08/2026) — un module par **domaine**, chacun
ayant sa propre raison de changer — et non un découpage par nature technique.
Chaque rubrique expose la même signature :

    collecter(ctx: ContexteFlux) -> list[FluxItem]

C'est ce contrat qui rend le découpage utile plutôt que cosmétique : ajouter une
rubrique au fil, c'est un module et une ligne dans `_COLLECTEURS` — pas une
treizième section à intercaler au milieu de 780 lignes.

| Module | Ce qui y change |
|---|---|
| `tickets` | ouvertures, changements d'état, réponses du CS, commentaires |
| `publications` | actualités, et leur règle d'archivage partagée avec /actualités |
| `evenements` | calendrier ; porte `TYPE_EMOJI`, réutilisé par l'agenda |
| `prestataires` | nouvelles fiches — page réservée au CS/admin |
| `communaute` | sondages, petites annonces, boîte à idées |
| `ressources` | questions fréquentes, documents partagés, diagnostics |
| `annuaire` | nouveaux membres du conseil syndical et du syndic |
| `sante` | indicateurs et agenda « Prochaines échéances » (aucune ligne de fil) |
| `epingles` | endpoint `/flux/epingles`, décompte du bandeau « Épinglé » |
| `commun` | contexte de collecte, périmètres, résumés, marqueurs |
| `schemas` | `FluxItem`, `FluxSante`, `FluxResponse`, `EpinglesCompte` |

## Ce qui a été factorisé, et ce qui a été laissé en double exprès

**Factorisé** — trois duplications que le fichier long avait fabriquées :

- la cascade de périmètre (`perimetre_cible` → `batiment_id` → défaut), recopiée
  cinq fois → `commun.perimetres_de` ;
- les cartes « réponse du CS » et « commentaire », identiques au caractère près
  hors trois valeurs, commentaire de six lignes compris → une seule écriture dans
  `tickets._carte_mise_a_jour`. C'est cette duplication qui a produit le bug du
  07/08/2026 : la clé de pièce jointe ajoutée d'un côté, oubliée de l'autre ;
- `TYPE_EMOJI`, défini une fois et partagé entre le fil et l'agenda.

**Laissé en double, volontairement** : les événements continuent d'appeler
`parse_perimetres(x.perimetre)` en direct. Ils n'ont pas de `perimetre_cible` et
leur règle ignore `batiment_id` — les faire passer par `perimetres_de` changerait
leur périmètre affiché dès qu'un bâtiment est renseigné. Le devis partageait cette
exception ; il n'y a plus qu'un cas, et une exception unique reste une exception. Deux règles qui se ressemblent ne sont pas la même règle
(`standards/02-factorisation.md` §4). Que `Evenement` ignore `batiment_id` est
peut-être un défaut en soi ; ce n'est pas à un découpage de le trancher.

## Ce qui n'a PAS changé

Les deux chemins (`GET /flux`, `GET /flux/epingles`), le contrat de sortie et
`main.py`, qui continue d'écrire `app.include_router(flux.router)` sans savoir
que ce module est devenu un paquet. Le préfixe `/flux` reste porté **ici**.

`_lien_document` et `_CATEGORIES_DOCUMENT_AVEC_LIEN` sont ré-exportés parce que
`api/tests/test_liens_front.py` les importe depuis `app.routers.flux` — les
laisser tomber aurait cassé le garde-fou qui protège contre le 404 du
26/07/2026.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import Utilisateur

from . import (
    annuaire,
    communaute,
    epingles,
    evenements,
    prestataires,
    publications,
    ressources,
    sante,
    tickets,
)
from .commun import ContexteFlux
from .schemas import EpinglesCompte, FluxItem, FluxResponse, FluxSante

#: Fenêtre glissante du fil, en jours — valeur reprise telle quelle du fichier
#: d'origine, où elle était écrite en dur sans justification. Un élément épinglé
#: y échappe (cf. `publications` et `evenements`).
_FENETRE_JOURS = 377

#: Les rubriques du fil, dans l'ordre de collecte. L'ordre d'affichage, lui, est
#: purement chronologique (tri global plus bas) : cette liste n'en décide pas.
_COLLECTEURS = (
    tickets.collecter,
    publications.collecter,
    evenements.collecter,
    prestataires.collecter,
    communaute.collecter,
    ressources.collecter,
    annuaire.collecter,
)

#  Le préfixe et le tag vivent ICI : les sous-routers déclarent des chemins nus,
#  donc identiques à ceux d'avant le découpage.
router = APIRouter(prefix="/flux", tags=["flux"])
router.include_router(epingles.router)


@router.get("", response_model=FluxResponse)
def get_flux(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    now = datetime.utcnow()
    ctx = ContexteFlux(
        session=session,
        user=user,
        now=now,
        since=now - timedelta(days=_FENETRE_JOURS),
    )

    items: list[FluxItem] = []
    for collecter in _COLLECTEURS:
        items.extend(collecter(ctx))
    items.sort(key=lambda x: x.date, reverse=True)

    return FluxResponse(items=items, sante=sante.calculer(ctx))


#  Surface publique conservée pour les importateurs externes (cf. docstring).
from .ressources import (  # noqa: E402  (après le montage du router, pour la lisibilité)
    _CATEGORIES_DOCUMENT_AVEC_LIEN,
    _lien_document,
)

__all__ = [
    "router",
    "ContexteFlux",
    "EpinglesCompte",
    "FluxItem",
    "FluxResponse",
    "FluxSante",
    "_CATEGORIES_DOCUMENT_AVEC_LIEN",
    "_lien_document",
]
