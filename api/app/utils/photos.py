"""Photos stockées en tableau JSON — lecture et filtrage, une seule fois.

Trois routeurs désérialisaient le même champ chacun de leur côté (flux, calendrier,
uploads), et le modèle porte déjà trois noms pour la même notion (`photos_urls`,
`photos_json`, `images_json`). On ne peut pas renommer les colonnes sans migration
de données, mais rien n'oblige à dupliquer la logique par-dessus.
"""
import json
from typing import Optional


def parse_photos(raw: Optional[str]) -> list[str]:
    """Tableau JSON stocké → liste d'URLs.

    Ne lève jamais : une valeur illisible en base ne doit pas faire échouer
    l'affichage de l'élément qui la porte. Le pire cas est une galerie vide.
    """
    if not raw:
        return []
    try:
        val = json.loads(raw) if isinstance(raw, str) else raw
        return [str(u) for u in val] if isinstance(val, list) else []
    except Exception:
        return []


def photos_internes(urls: list[str]) -> list[str]:
    """Ne conserve que les URLs produites par notre propre endpoint d'upload.

    Sans ce filtre, une requête de modification pourrait injecter une URL
    arbitraire, servie ensuite dans un `<img src>` : au premier affichage, chaque
    résident révélerait son adresse IP à un tiers, avec un contenu hors de notre
    contrôle. Les champs de photos exposés en écriture ne servent qu'à RETIRER des
    images déjà téléversées — tout le reste est écarté sans discussion.
    """
    return [
        str(u) for u in urls
        if str(u).startswith("/uploads/") and ".." not in str(u)
    ]
