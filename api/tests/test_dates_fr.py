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


# ── Durées : `jj:hh:mm`, et une seule écriture ────────────────────────────────
#
# POURQUOI (01/09/2026, demandé à l'écran) : le fil affichait « Résolu en 23.9h »
# — un arrondi décimal d'heures, qui n'a de sens nulle part ailleurs sur le site
# et qu'il faut convertir de tête pour lire 23 h 54. Le séparateur décimal était
# en prime un point, sur un site intégralement en français.

def test_duree_jhm_rend_le_format_demande():
    """`jj:hh:mm`, sur deux chiffres, jusqu'au-delà de 99 jours."""
    from datetime import timedelta

    from app.utils.dates_fr import duree_jhm

    cas = [
        (timedelta(hours=23, minutes=54), "00:23:54"),
        (timedelta(days=2, hours=3, minutes=15), "02:03:15"),
        (timedelta(minutes=7), "00:00:07"),
        #  Les secondes ne remontent PAS d'un cran : 59 s reste « 00:00:00 ».
        #  Arrondir ferait dire « une minute » à ce qui n'en est pas une, et la
        #  minute est la plus petite unité que ce format affiche.
        (timedelta(seconds=59), "00:00:00"),
        #  Au-delà de 99 jours le champ déborde à trois chiffres, et c'est voulu :
        #  tronquer afficherait « 00:01:00 » pour un ticket vieux de cent jours.
        (timedelta(days=100, hours=1), "100:01:00"),
    ]
    for ecart, attendu in cas:
        assert duree_jhm(ecart) == attendu, f"{ecart!r} devrait rendre {attendu}"


def test_duree_jhm_distingue_le_zero_de_l_incoherence():
    """🔴 Le cas zéro de cette fonction, et c'est celui qui a produit un défaut.

    Zéro est une durée VALIDE — un ticket résolu dans la minute. L'ancien code
    testait `if duree` sur un float arrondi à `0.0` : la mention disparaissait
    pour le ticket le plus vite résolu, le seul à ne pas dire son temps.

    Une durée NÉGATIVE, elle, est une donnée incohérente (fermeture antérieure à
    la création). L'afficher « -1:00:00 » habillerait le défaut ; on rend `None`,
    et l'appelant n'affiche rien.
    """
    from datetime import timedelta

    from app.utils.dates_fr import duree_jhm

    assert duree_jhm(timedelta(0)) == "00:00:00"
    assert duree_jhm(timedelta(seconds=-1)) is None
    assert duree_jhm(timedelta(days=-3)) is None


def test_aucune_duree_en_heures_decimales_dans_app():
    """Une durée AFFICHÉE se formate par `duree_jhm`, jamais à la main.

    Le motif vise la conversion en heures décimales suivie d'un arrondi — la
    forme exacte qui produisait « 23.9h ». Un calcul de durée à des fins de
    STATISTIQUE reste permis (`flux/sante.py` en moyenne une population) : ce
    n'est pas un format, personne ne le lit tel quel.

    ⚠️ Le contrôle porte donc sur la mise en forme, pas sur le calcul — et il le
    dit, plutôt que d'interdire `total_seconds()` en bloc, ce qui l'aurait fait
    désarmer au premier usage légitime.
    """
    import re

    motif = re.compile(r"round\(\s*\([^)]*\)\.total_seconds\(\)\s*/\s*3600")
    fautifs: list[str] = []
    for chemin in sorted(_APP_DIR.rglob("*.py")):
        for num, ligne in enumerate(
            chemin.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if motif.search(ligne):
                fautifs.append(f"{chemin.relative_to(_APP_DIR.parent)}:{num}: {ligne.strip()}")

    assert not fautifs, (
        "Durée arrondie en heures décimales — c'est la forme qui affichait "
        "« Résolu en 23.9h ». Passer par `dates_fr.duree_jhm()` :\n" + "\n".join(fautifs)
    )
