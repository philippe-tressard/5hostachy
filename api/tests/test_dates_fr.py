"""Garde-fou préventif : aucune date affichée ne doit dépendre de la locale.

`strftime('%B')` / `%A` traduisent selon `LC_TIME`. L'image `python:3.12-slim` ne
génère aucune locale au-delà de C/POSIX : le mois sortait donc en anglais dans un
document français (« Voté en AG 2026 — 12 June 2026 » sur la fiche arrivant,
signalé le 26/07/2026), ainsi que dans les e-mails publications / tickets et les
alertes de santé.

Ce test verrouille les deux bouts :
1. `dates_fr` produit bien du français, quelle que soit la locale du process ;
2. aucun `%B`/`%b`/`%A`/`%a` ne réapparaît dans `app/` — c'est ce point qui évite
   la récidive, le correctif ne tenant pas si un futur appel réintroduit `%B`.
"""
import locale as _locale
import re
from datetime import date, datetime
from pathlib import Path

from app.utils.dates_fr import (
    date_courte,
    date_longue,
    datetime_longue,
    datetime_longue_paris,
    jour_longue,
)

_APP_DIR = Path(__file__).resolve().parents[1] / "app"

# Directives strftime traduites selon LC_TIME (mois et jours, longs et abrégés).
_DIRECTIVES_LOCALISEES = re.compile(r"%[-#]?[BbAa]")


def test_date_longue_en_francais():
    assert date_longue(date(2026, 6, 12)) == "12 juin 2026"
    assert date_longue(date(2026, 8, 1)) == "1 août 2026"  # pas de zéro devant


def test_datetime_longue_en_francais():
    assert datetime_longue(datetime(2026, 6, 12, 9, 5)) == "12 juin 2026 à 09:05"


def test_jour_longue_en_francais():
    assert jour_longue(date(2026, 7, 25)) == "samedi 25 juillet 2026"


def test_date_courte():
    """Format numérique — zéros de tête conservés (ex-`strftime('%d/%m/%Y')`)."""
    assert date_courte(date(2026, 7, 5)) == "05/07/2026"
    assert date_courte(date(2026, 12, 31)) == "31/12/2026"


def test_datetime_longue_paris_applique_le_decalage():
    """Horodatage naïf UTC de la base → heure de Paris (ex-`_fmt_paris` dupliqué).

    Été : UTC+2 · hiver : UTC+1 — c'est le décalage qui est vérifié, pas le
    formatage (couvert au-dessus).
    """
    assert datetime_longue_paris(datetime(2026, 7, 25, 8, 5)) == "25 juillet 2026 à 10:05"
    assert datetime_longue_paris(datetime(2026, 1, 15, 8, 5)) == "15 janvier 2026 à 09:05"


def test_tous_les_mois_traduits():
    """Aucun mois ne doit fuiter en anglais (table complète et bien ordonnée)."""
    rendus = [date_longue(date(2026, m, 1)) for m in range(1, 13)]
    assert [r.split()[1] for r in rendus] == [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]


def test_insensible_a_la_locale_du_process():
    """Le rendu ne change pas si le process tourne en locale C (cas du conteneur)."""
    precedente = _locale.setlocale(_locale.LC_TIME)
    try:
        _locale.setlocale(_locale.LC_TIME, "C")
        assert date_longue(date(2026, 6, 12)) == "12 juin 2026"
    finally:
        _locale.setlocale(_locale.LC_TIME, precedente)


def test_aucune_directive_strftime_localisee_dans_app():
    """Interdit `%B`/`%A`… dans `app/` : en locale C ils sortent en anglais.

    Si ce test échoue, remplacer l'appel par `dates_fr.date_longue()` /
    `datetime_longue()` — ne pas générer une locale fr_FR dans l'image (correctif
    fragile, cf. docstring de `app/utils/dates_fr.py`).
    """
    fautifs: list[str] = []
    for chemin in sorted(_APP_DIR.rglob("*.py")):
        if chemin.name == "dates_fr.py":
            continue  # documente l'interdiction : cite `%B` en prose
        for num, ligne in enumerate(
            chemin.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if "strftime" not in ligne and "%" not in ligne:
                continue
            if _DIRECTIVES_LOCALISEES.search(ligne):
                rel = chemin.relative_to(_APP_DIR.parent)
                fautifs.append(f"{rel}:{num}: {ligne.strip()}")

    assert not fautifs, (
        "Format de date dépendant de la locale (mois/jour en anglais en prod) :\n"
        + "\n".join(fautifs)
    )
