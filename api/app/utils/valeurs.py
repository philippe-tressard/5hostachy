"""La valeur d'une énumération `str, Enum` — qu'on tienne l'énumération ou la chaîne.

## Pourquoi une fonction, et une seule

Les champs `categorie`, `statut`, `priorite`, `type`… portent tantôt l'énumération
(un corps de requête validé par Pydantic, un objet neuf), tantôt la chaîne (une
ligne relue en base, un brouillon d'aperçu). Or :

    str(CategorieTicket.etude_travaux)  →  'CategorieTicket.etude_travaux'

Le défaut est revenu au moins deux fois — `CategorieTicket.panne` rendu dans un
courriel, puis le kanban des affaires jamais alimenté (#1092, 23/09/2026), parce
que `suivi_par_defaut` comparait `str(categorie)`. L'idiome qui l'évite,
`getattr(x, "value", x)`, était écrit NEUF fois : il vit ici désormais.
🔒 `test_valeur_source_unique.py` refuse une dixième copie.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


def valeur(x: Any) -> Any:
    """`x.value` si `x` est une énumération, sinon `x` tel quel (`None` compris)."""
    return x.value if isinstance(x, Enum) else x


__all__ = ["valeur"]
