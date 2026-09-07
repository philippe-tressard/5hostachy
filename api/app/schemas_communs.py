"""Le socle des schémas — ce dont tous les autres ont besoin, et qui ne dépend de rien.

Extrait de `schemas.py` le 19/08/2026 : le fichier venait de franchir les 500
lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé qu'il
grossisse pour recevoir le périmètre d'une évolution (#497).

⚠️ **Ce module n'importe RIEN du projet, et c'est sa raison d'être.** C'est ce
qui permet à `schemas_tickets.py` de s'en servir sans dépendre de `schemas.py`,
qui l'importe lui-même — un cycle rendrait l'ordre de chargement décisif pour le
démarrage de l'application.
"""
import json
from typing import Annotated, List

from pydantic import BeforeValidator



def liste_depuis_json(v):
    """Colonne texte contenant un tableau JSON → liste d'URLs.

    Quatre schémas portaient ce même validateur recopié (`photos_urls`,
    `fichiers_urls` × 3). C'est la contrepartie côté pydantic de
    `app/utils/photos.parse_photos`, que les routeurs utilisent pour lire les
    mêmes colonnes : deux points d'entrée, une seule règle.

    Ne lève jamais : une valeur illisible en base ne doit pas faire échouer la
    lecture de l'élément qui la porte. Le pire cas est une liste vide.

    Publique (et non `_privée`) depuis le 16/08/2026 : le détail d'un sondage
    construit sa réponse à la main, sans `response_model`, et devait donc appeler
    la règle plutôt que la réécrire.
    """
    if v is None:
        return []
    if isinstance(v, str):
        try:
            charge = json.loads(v)
        except Exception:
            return []
        return [str(u) for u in charge] if isinstance(charge, list) else []
    return v


#: Champ exposé en liste, stocké en colonne texte. `Optional[ListeJson]` reste
#: possible là où l'absence et la liste vide doivent se distinguer.
#:
#: ⚠️ Ce type s'appelait `ListeJson` — un nom qui décrivait ses trois premiers
#: usages (photos, fichiers) et non ce qu'il fait. Le ciblage des sondages avait
#: exactement le même besoin pour des CODES de périmètre : soit on importait un
#: type nommé « URLs » pour des périmètres, soit on en écrivait un second,
#: identique. Renommé pour ce qu'il est — une liste sérialisée en JSON.
ListeJson = Annotated[List[str], BeforeValidator(liste_depuis_json)]
