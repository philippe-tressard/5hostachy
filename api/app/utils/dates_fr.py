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
