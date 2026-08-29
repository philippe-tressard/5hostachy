"""L'échéance d'un contrat se déduit, elle ne se saisit pas.

Signalé par l'utilisateur le 29/08/2026 : *« pour l'échéance d'assurance, si
celui-ci n'est pas stoppé, il est automatiquement reconduit — ne faudrait-il pas
supprimer l'année ? »*

La réponse retenue conserve l'année et la rend TOUJOURS juste, par report d'un an
tant que le terme est passé. Le raisonnement complet — et les trois valeurs
différentes que « échéance » désignait selon l'écran — est dans le module
`app/utils/echeance_contrat.py`.

⚠️ Tous les cas fixent `aujourdhui` : un test qui dépend de la date d'exécution
passe au vert ou au rouge selon le mois, et n'éprouve alors plus rien
(`standards/04` §1 — un contrôle qui ne mesure pas ce qu'on croit).
"""
from datetime import date

import pytest

from app.utils.echeance_contrat import echeance_du_contrat

REFERENCE = date(2026, 8, 29)


class _Contrat:
    def __init__(self, debut, valeur=None, unite=None):
        self.date_debut = debut
        self.duree_initiale_valeur = valeur
        self.duree_initiale_unite = unite


def test_sans_date_de_debut_aucune_echeance():
    """Le cas zéro : on ne devine pas un terme à partir de rien.

    ⚠️ Un repli sur « aujourd'hui + 1 an » afficherait une échéance INVENTÉE,
    que le CS prendrait pour une donnée. Rendre `None` fait disparaître la ligne,
    ce qui est le comportement honnête.
    """
    assert echeance_du_contrat(_Contrat(None), REFERENCE) is None


def test_un_terme_a_venir_n_est_pas_reconduit():
    """Mandat de trois ans commencé en 2024 : terme en 2027, jamais atteint."""
    e = echeance_du_contrat(_Contrat(date(2024, 6, 1), 3, "ans"), REFERENCE)
    assert e.date == date(2027, 6, 1)
    assert e.reconduit is False, "un terme non atteint n'est pas une reconduction"


def test_un_terme_passe_se_reporte_et_le_dit():
    """🔴 LE CŒUR DE LA DEMANDE. Assurance de 2020 : le terme court toujours.

    Sans le report, la fiche affichait « échéance 17/12/2020 » — une date passée
    depuis six ans, qui se lit comme un contrat EXPIRÉ alors qu'il est
    tacitement reconduit chaque année.
    """
    e = echeance_du_contrat(_Contrat(date(2020, 12, 17)), REFERENCE)
    assert e.date == date(2026, 12, 17), "l'anniversaire est conservé, l'année suit"
    assert e.reconduit is True


def test_le_report_franchit_l_annee_quand_l_anniversaire_est_deja_passe():
    """Anniversaire en février, on est en août : le terme est en février PROCHAIN.

    ⚠️ Le cas que le précédent ne couvre pas : là, le report doit dépasser
    l'année courante. Un `while` mal borné rendrait février 2026, déjà passé.
    """
    e = echeance_du_contrat(_Contrat(date(2019, 2, 3)), REFERENCE)
    assert e.date == date(2027, 2, 3)


def test_le_terme_du_jour_meme_est_reporte():
    """Une échéance qui tombe aujourd'hui est déjà arrivée : elle se reporte.

    La borne est `<=` et non `<`, et c'est délibéré : afficher « échéance
    aujourd'hui » sur un contrat que personne n'a dénoncé le fait passer pour
    une urgence alors qu'il vient d'être reconduit.
    """
    e = echeance_du_contrat(_Contrat(date(2025, 8, 29)), REFERENCE)
    assert e.date == date(2027, 8, 29)
    assert e.reconduit is True


@pytest.mark.parametrize(
    "debut,valeur,unite,attendu",
    [
        (date(2026, 1, 31), 1, "mois", date(2027, 2, 28)),
        (date(2024, 1, 31), 1, "mois", date(2027, 2, 28)),
        (date(2023, 8, 31), 6, "mois", date(2027, 2, 28)),
    ],
)
def test_un_jour_qui_n_existe_pas_dans_le_mois_cible_est_ramene(debut, valeur, unite, attendu):
    """31 janvier + 1 mois n'existe pas — sans ramené, la dérivation LÈVE.

    ⚠️ Un défaut qui ne se manifesterait que sur les contrats commencés un 29,
    30 ou 31 : sept jours de l'année, donc jamais en essai, et une page blanche
    en production le jour où quelqu'un saisit la bonne date.
    """
    assert echeance_du_contrat(_Contrat(debut, valeur, unite), REFERENCE).date == attendu


def test_une_duree_inconnue_vaut_annuelle():
    """Convention conservée du reporting (#453), et elle est délibérée.

    Rendre `None` ferait DISPARAÎTRE des relances le contrat dont on ne connaît
    pas la durée — c'est-à-dire exactement celui qu'il faut regarder.
    """
    e = echeance_du_contrat(_Contrat(date(2026, 3, 15)), REFERENCE)
    assert e.date == date(2027, 3, 15)


def test_les_deux_sections_de_la_fiche_recoivent_LE_MEME_enrichissement():
    """🔴 L'invariant du fichier : assurance et syndic sont LE MÊME GESTE.

    `_echeance_lue` sert les deux. Le jour où quelqu'un donne un enrichissement
    à l'une sans le donner à l'autre, ce test le dit — c'est `standards/02` §2
    rendu exécutoire, comme le fait déjà `test_contrats_de_reference`.
    """
    import ast
    import pathlib

    source = pathlib.Path(__file__).parent.parent / "app" / "routers" / "copropriete.py"
    arbre = ast.parse(source.read_text(encoding="utf-8"))
    appels = {
        fn.name: [
            n.args[0].value
            for n in ast.walk(fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "_echeance_lue"
            and n.args
            and isinstance(n.args[0], ast.Constant)
        ]
        for fn in ast.walk(arbre)
        if isinstance(fn, ast.FunctionDef) and fn.name.endswith("_du_contrat")
    }
    assert appels.get("assurance_du_contrat") == ["assurance"], appels
    assert appels.get("syndic_du_contrat") == ["syndic"], appels
