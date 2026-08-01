"""Garde-fou : un montant s'affiche pareil partout, backend comme front.

Le front a `fmtMontant()` depuis que le rendu de `montant_estime` avait dérivé en
trois écritures sur une même page. Le backend n'avait rien : `flux.py` formatait
à la main, deux fois, et avec **deux conventions différentes** — un `:,.0f` qui
arrondissait à l'entier, et deux séparateurs de milliers distincts (espace
ordinaire pour les devis, espace fine insécable pour les annonces).

Conséquence mesurée le 01/08/2026 : un devis à 1 234,50 € s'affichait
« 1 234 € » dans le fil d'activité et « 1 234,50 € » sur la page Prestataires.
Même champ, deux vérités selon l'écran.

Ce test verrouille le rendu ET interdit qu'un futur formatage monétaire
réapparaisse à la main dans `app/` — c'est le second point qui évite la récidive,
le correctif ne tenant pas si un prochain appel réintroduit un `:,.0f €`.
"""
import re
from pathlib import Path

import pytest

from app.utils.montants import montant_fr

_APP_DIR = Path(__file__).resolve().parents[1] / "app"

# Une f-string qui colle un format numérique à un symbole euro : exactement ce
# que ce module existe pour remplacer.
_MONTANT_A_LA_MAIN = re.compile(r":[,\.]?\d*[,\.]?\d*f\}\s*(€|\\u20ac)")


@pytest.mark.parametrize(
    "valeur,attendu",
    [
        (None, "—"),
        (0, "0 €"),
        (1234, "1 234 €"),          # rond : pas de « ,00 »
        (1234.5, "1 234,50 €"),     # décimales conservées
        (1234.567, "1 234,57 €"),   # arrondi au centime
        (999999.99, "999 999,99 €"),
    ],
)
def test_montant_fr(valeur, attendu):
    assert montant_fr(valeur) == attendu


def test_separateur_insecable():
    """Un montant ne doit jamais se couper en fin de ligne."""
    assert " " not in montant_fr(1234.5)


def test_aucun_montant_formate_a_la_main_dans_app():
    fautifs = []
    for chemin in sorted(_APP_DIR.rglob("*.py")):
        for n, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
            if _MONTANT_A_LA_MAIN.search(ligne):
                fautifs.append(f"{chemin.relative_to(_APP_DIR).as_posix()}:{n}: {ligne.strip()[:90]}")
    assert not fautifs, (
        "Montant formaté à la main — utiliser `app.utils.montants.montant_fr()`, "
        "sous peine de voir le même champ rendu différemment selon l'écran :\n"
        + "\n".join(fautifs)
    )
