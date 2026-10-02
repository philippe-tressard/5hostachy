"""Lire un objet pour le RENDRE : partir du modèle, n'ajouter que ce qui se calcule.

## Pourquoi cette aide existe (#1092, #1563)

Construire un schéma de sortie colonne par colonne —
`LotRead(id=lot.id, numero=lot.numero, …)` — perd en silence tout champ déclaré
au schéma et oublié dans l'appel : il prend sa valeur par défaut. `ticket_read`
a ainsi perdu `debut`, `fin`, `suivi_kanban` (#1092), et l'historique d'une
affaire `assiste_ia` et `contenu_origine` (#1563).

`Schema.model_validate(objet)` ne suffit pas toujours : beaucoup de schémas
déclarent OBLIGATOIRES des champs qui se calculent (le `parent` d'un
périmètre, le nom d'un bailleur), et la validation échouerait avant qu'on ait
pu les fournir. Cette aide lit sur l'objet chaque champ du schéma qu'il porte,
y substitue les champs dérivés, et valide le tout — dérivés compris.

🔒 `tests/test_lecture_colonne_par_colonne.py` refuse la recopie.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

S = TypeVar("S", bound=BaseModel)


def lire_objet(schema: type[S], objet: Any, **derives: Any) -> S:
    """`schema` rempli depuis les attributs d'`objet`, puis les `derives`.

    Un dérivé que le schéma ne déclare pas LÈVE : Pydantic l'ignorerait, et le
    champ n'atteindrait jamais l'API (`test_schemas_champs`, même défaut).
    Un champ dérivé n'est pas lu sur l'objet — une relation homonyme ne se
    charge donc pas pour rien.
    """
    champs = schema.model_fields
    inconnus = derives.keys() - champs.keys()
    if inconnus:
        raise TypeError(f"{schema.__name__} ne déclare pas : {', '.join(sorted(inconnus))}")
    lus = {nom: getattr(objet, nom) for nom in champs if nom not in derives and hasattr(objet, nom)}
    return schema.model_validate({**lus, **derives})
