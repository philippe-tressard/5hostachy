"""Formatage des dates en français, indépendant de la locale du système.

`strftime('%B')` (mois) et `%A` (jour) traduisent selon `LC_TIME`. L'image
`python:3.12-slim` ne génère **aucune** locale au-delà de C/POSIX : en production
le mois sortait donc en anglais — « Voté en AG 2026 — 12 June 2026 » sur la fiche
arrivant, un document destiné aux résidents et intégralement en français.

Générer une locale `fr_FR.UTF-8` dans le Dockerfile serait un correctif fragile :
il se reperdrait au premier changement d'image de base, ne protégerait pas les
tests lancés hors conteneur, et laisserait le piège en place pour le prochain
`%B` écrit ailleurs. On formate donc depuis une table explicite — le résultat ne
dépend plus de l'environnement d'exécution.

**Ne jamais utiliser `%B`, `%b`, `%A` ni `%a` dans ce projet** : passer par
`date_longue()` / `datetime_longue()`. `tests/test_dates_fr.py` échoue si un
format dépendant de la locale réapparaît dans `app/`.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ_PARIS = ZoneInfo("Europe/Paris")
_TZ_UTC = ZoneInfo("UTC")

MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def date_longue(d: date | datetime) -> str:
    """`date(2026, 7, 25)` → `25 juillet 2026`."""
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def datetime_longue(dt: datetime) -> str:
    """`datetime(2026, 7, 25, 9, 5)` → `25 juillet 2026 à 09:05`.

    Remplace `strftime('%-d %B %Y à %H:%M')` (mois anglais hors locale fr, et
    `%-d` est une extension glibc absente sous Windows).
    """
    return f"{date_longue(dt)} à {dt:%H:%M}"


def jour_longue(d: date | datetime) -> str:
    """`date(2026, 7, 25)` → `samedi 25 juillet 2026`."""
    return f"{JOURS[d.weekday()]} {date_longue(d)}"


def date_courte(d: date | datetime) -> str:
    """`date(2026, 7, 25)` → `25/07/2026`.

    Format numérique pour les tableaux et documents denses (historiques de
    tickets). Indépendant de la locale — aucun nom de mois — mais centralisé ici
    pour que tout formatage de date destiné à l'affichage passe par ce module.
    """
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def datetime_longue_paris(dt: datetime) -> str:
    """Horodatage **naïf UTC** (tel que stocké en base) → texte français heure de Paris.

    `datetime(2026, 7, 25, 8, 5)` → `25 juillet 2026 à 10:05`.

    Était dupliqué à l'identique sous le nom `_fmt_paris` dans `routers/tickets.py`
    et `routers/publications.py` (corps des e-mails). Les horodatages de la base
    sont naïfs et en UTC : c'est ce module qui porte cette convention, pour que le
    décalage ne soit pas réécrit à chaque point d'appel.
    """
    return datetime_longue(dt.replace(tzinfo=_TZ_UTC).astimezone(TZ_PARIS))


def mois_ecoules(depuis: datetime, maintenant: datetime | None = None) -> int:
    """Nombre de mois **entiers** écoulés depuis `depuis` (horodatage naïf UTC).

    Compte des mois calendaires, pas des tranches de 30 jours : entre le 31/01 et
    le 28/02 il s'est écoulé un mois, ce qu'une division par 30 jours nierait.
    """
    ref = maintenant or datetime.utcnow()
    mois = (ref.year - depuis.year) * 12 + (ref.month - depuis.month)
    if (ref.day, ref.hour, ref.minute) < (depuis.day, depuis.hour, depuis.minute):
        mois -= 1
    return max(0, mois)


def formule_anciennete(mois: list[int]) -> str:
    """Formule française décrivant l'ancienneté d'un lot de dossiers.

    `[1]` → « plus d'un mois » · `[4, 4]` → « plus de 4 mois » · `[1, 5]` → « un à 5 mois »

    Sert le préambule de la relance syndic : un chiffre exact se conteste mal,
    alors qu'un « depuis un certain temps » s'ignore sans effort. La forme au
    pluriel n'est employée que si elle est vraie — annoncer « 3 à 3 mois » ou
    « plus de 1 mois » décrédibiliserait le reste du courrier.

    Volontairement brève : la même formule alimente le corps ET l'objet du mail,
    que les clients de messagerie tronquent vers 70 caractères. Une seule
    formule, donc, plutôt qu'une version longue et une version courte à tenir
    d'accord.
    """
    if not mois:
        return "plus d'un mois"
    mini, maxi = min(mois), max(mois)
    if maxi < 2:
        return "plus d'un mois"
    if mini == maxi:
        return f"plus de {maxi} mois"
    if mini < 2:
        return f"un à {maxi} mois"
    return f"{mini} à {maxi} mois"
