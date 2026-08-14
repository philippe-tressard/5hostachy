"""Les bâtiments d'un utilisateur — au sens large, et pour un seul usage.

## Ce que ce module sert, et ce qu'il ne sert pas

Il répond à « quels bâtiments sont les MIENS ? », question posée par la préférence
« n'afficher que les contenus de mes bâtiments » (#339). Un copropriétaire peut
détenir des lots dans plusieurs bâtiments : `Utilisateur.batiment_id`, qui est
unique, ne suffit donc pas à répondre.

⚠️ **Cette liste ne décide jamais d'un accès.** Elle sert exclusivement à
restreindre ce qu'un utilisateur a demandé à ne plus voir — donc à lui montrer
**moins**, jamais plus. La règle qui décide de la visibilité d'un document, d'un
sondage ou d'une AG continue de s'appuyer sur le seul `batiment_id`
(`utils/visibility.perimetre_visible`), et il faut qu'il en reste ainsi : élargir
la notion de « mes bâtiments » à mes lots au milieu d'une décision d'accès
ouvrirait des contenus réservés à quelqu'un qui ne les voyait pas.

C'est la contrainte posée par l'utilisateur le 14/08/2026 : *une agence, un
bailleur ou un mandataire qui n'avaient pas de visibilité n'en gagnent aucune.*
L'ouverture porte sur l'axe **bâtiment**, jamais sur l'axe **public**.

## Le cache

Même parti pris que `utils/perimetres.arbre()` : une durée courte, et **aucune
mise en cache d'un résultat obtenu sur une base indisponible** — figer une liste
vide masquerait le rétablissement, et une liste vide vaut ici « je ne sais pas ».
"""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger("hostachy.mes_batiments")

#: Assez court pour qu'un lot ajouté se voie vite, assez long pour ne pas
#: interroger la base à chaque élément d'une liste de cinquante actualités.
_TTL_SECONDES = 30.0

_cache: dict[int, tuple[float, frozenset[int]]] = {}


def invalider_cache(user_id: Optional[int] = None) -> None:
    """À appeler après une écriture sur `user_lot` — ou entièrement, sans argument."""
    if user_id is None:
        _cache.clear()
    else:
        _cache.pop(user_id, None)


def batiments_de_l_utilisateur(user) -> frozenset[int]:
    """Les bâtiments de son rattachement **et** de ses lots actifs.

    Renvoie un ensemble **vide** si rien n'est connu — ce que l'appelant doit
    traiter comme « aucune restriction possible », et non comme « aucun accès » :
    un utilisateur sans bâtiment ni lot qui coche la restriction ne doit pas se
    retrouver devant un fil vide (cas zéro, `standards/04` §2).
    """
    user_id = getattr(user, "id", None)
    connus: set[int] = set()
    if getattr(user, "batiment_id", None) is not None:
        connus.add(user.batiment_id)

    if user_id is None:
        return frozenset(connus)

    entree = _cache.get(user_id)
    if entree is not None and (time.monotonic() - entree[0]) < _TTL_SECONDES:
        return entree[1] | frozenset(connus)

    try:
        from sqlmodel import select

        from app.database import SessionLocal
        from app.models.copropriete import Lot
        from app.models.core import UserLot

        with SessionLocal() as session:
            lignes = session.exec(
                select(Lot.batiment_id)
                .join(UserLot, UserLot.lot_id == Lot.id)
                .where(UserLot.user_id == user_id, UserLot.actif == True)  # noqa: E712
            ).all()
        #  `batiment_id` est nul sur un lot de parking : un parking n'est pas un
        #  bâtiment et ne doit pas entrer dans la liste.
        des_lots = frozenset(b for b in lignes if b is not None)
    except Exception as exc:
        #  Pas de mise en cache : la base reviendra, et une liste figée à vide
        #  ferait durer la panne au-delà d'elle-même.
        logger.error(
            "Lots de l'utilisateur %s illisibles (%s) — seul son bâtiment de "
            "rattachement est retenu", user_id, exc,
        )
        return frozenset(connus)

    _cache[user_id] = (time.monotonic(), des_lots)
    return des_lots | frozenset(connus)
