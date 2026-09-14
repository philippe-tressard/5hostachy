"""Ce qu'un badge OUVRE, et comment on le devine quand personne ne l'a dit.

## La règle (14/09/2026, #953)

> « par défaut le bâtiment du logement possédé ; exceptionnellement certains
>   badges ont accès à tous les bâtiments »
>
> puis : « si le vigik est résolu à un propriétaire, alors étends-le, sauf s'il
>   possède plusieurs appartements »

## Pourquoi une fonction PURE

La même décision se prend à trois moments — la migration de reprise, la création
d'un badge par le conseil syndical, et la résolution d'une ligne d'import. Écrite
trois fois, elle divergerait au premier ajustement : c'est exactement ce qui est
arrivé au `lot_id` de la télécommande, recopié d'un côté et pas de l'autre
(corrigé en v1.36.8).

Isolée ici, elle s'éprouve sans base ni session — le motif que `standards/04` §11
impose aux décisions d'infra, appliqué à une règle métier.

⚠️ La migration 0190 en porte l'équivalent **en SQL**, et ne peut pas appeler
cette fonction : une migration ne doit pas importer le code de l'application, qui
change alors qu'elle non. Les deux écritures sont donc assumées, et
`test_acces_perimetre.py` vérifie qu'elles décrivent le même comportement sur les
mêmes cas.
"""
from __future__ import annotations

from typing import Iterable, Optional

#: Le préfixe d'un code de périmètre de bâtiment — la convention du seed.
#:
#: ⚠️ Il est écrit ici parce qu'on CONSTRUIT un code, pas parce qu'on en
#: reconnaît un : `perimetreDuBatiment` (front) interroge l'arbre pour lire, et
#: c'est la bonne façon de lire. Écrire demande une convention, et elle est
#: celle du seed.
PREFIXE_BATIMENT = "bat:"


def code_batiment(batiment_id: int) -> str:
    """Le code de périmètre d'un bâtiment : `bat:3`."""
    return f"{PREFIXE_BATIMENT}{batiment_id}"


def acces_deduit(batiments: Iterable[Optional[int]]) -> Optional[list[str]]:
    """L'accès déduit des bâtiments où la personne a des lots.

    >>> acces_deduit([2])
    ['bat:2']
    >>> acces_deduit([2, 2, 2])
    ['bat:2']
    >>> acces_deduit([2, 3]) is None
    True
    >>> acces_deduit([]) is None
    True
    >>> acces_deduit([None]) is None
    True
    >>> acces_deduit([2, None])
    ['bat:2']

    🔴 **UN SEUL bâtiment, pas un seul appartement** — et c'est un élargissement
    assumé de la consigne, qui disait « sauf s'il possède plusieurs appartements ».

    Un accès ouvre un **bâtiment**, pas une porte d'appartement : quelqu'un qui
    possède les lots 210 et 212 du bâtiment 2 n'introduit aucune ambiguïté sur ce
    que son badge doit ouvrir. Refuser là perdrait une information pour rien.

    ⚠️ Deux bâtiments rendent le choix impossible, et on rend alors **`None`** —
    *« on ne sait pas »*. Choisir le premier serait une décision déguisée en
    donnée, sur un droit d'accès physique. C'est le seul sens dans lequel se
    tromper est rattrapable : une case vide se remarque, un mauvais bâtiment non.

    ⚠️ Les lots **sans bâtiment** (une place de parking) sont ignorés, pas
    comptés comme une seconde valeur : ils ne disent rien du bâtiment, et les
    compter ferait échouer la déduction pour un propriétaire d'appartement qui a
    aussi un parking — c'est-à-dire presque tout le monde.
    """
    distincts = {b for b in batiments if b is not None}
    if len(distincts) != 1:
        return None
    return [code_batiment(distincts.pop())]
