"""**L'heure du serveur, écrite une fois.**

## Pourquoi ce module (#1047, 25/09/2026)

`datetime.utcnow()` était appelé **114 fois** dans `app/` — dont 51 en
`default_factory` de modèle —, sans helper. Il est **déprécié depuis Python
3.12**, l'image de l'API (`python:3.12-slim`), et chaque appel émet un
`DeprecationWarning` : le jour où il disparaîtra, ce sont 114 lignes à
reprendre, et on en manquera.

## 🔴 UTC NAÏF — et c'est voulu

Le ticket proposait `datetime.now(timezone.utc)`. Ce n'est **pas** un
remplacement : `utcnow()` rend une date **naïve** (sans fuseau), `now(utc)` une
date **consciente**, et Python refuse de comparer les deux (`TypeError`).

Or tout ce que la base rend est naïf — SQLite ne stocke pas de fuseau —, et le
dépôt entier tient cette convention : `whatsapp_scheduler`,
`telemetry_aggregation`, `courriel_boite` et `telemetry` ramènent explicitement
leurs dates à l'UTC naïf par `.replace(tzinfo=None)`. Passer d'un coup à des
dates conscientes aurait fait lever chaque comparaison entre « maintenant » et
une date lue en base.

`maintenant()` rend donc **exactement** ce que rendait `utcnow()`, sans
l'avertissement. Passer aux dates conscientes serait une autre décision — base,
modèles et comparaisons ensemble —, pas un remplacement de fonction.

🔒 Ruff `DTZ003` refuse `utcnow()` dans `api/app/` (CI, job `lint-backend`).

⚠️ **S'appelle par son module** — `horloge.maintenant()`, jamais importée seule :
treize fichiers ont déjà une variable ou un paramètre nommé `maintenant`
(`maintenant = maintenant or …`), qu'une fonction du même nom aurait masqué.
"""

from __future__ import annotations

from datetime import datetime, timezone


def maintenant() -> datetime:
    """L'instant présent, en **UTC naïf** — la forme de toutes les dates en base.

    Sert aussi de `default_factory` : `Field(default_factory=horloge.maintenant)`.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
