"""Ce dont les tests de rendu PDF ont besoin des deux côtés.

Ces trois objets existaient dans `test_documents_pdf.py` seulement. Le jour où
un second fichier de test a eu besoin du même garde (`test_pdf_hors_process.py`,
16/09/2026), les recopier aurait fabriqué la duplication que ce dépôt refuse —
et, plus concrètement, deux définitions de « WeasyPrint est-il là ? » qui
divergeraient au premier changement d'image.

⚠️ `EN_INTEGRATION_CONTINUE` n'est pas une commodité : c'est ce qui empêche
l'abstention d'être silencieuse. Sur un poste Windows, WeasyPrint n'a pas ses
bibliothèques système (pango, cairo) et sauter est légitime ; en CI, sauter
signifierait que le rendu n'est contrôlé **nulle part**. Chaque fichier qui se
sert de `besoin_weasyprint` doit donc porter son test de portée — cf.
`test_documents_pdf.py::test_weasyprint_present_en_ci` et son jumeau ici.
Un contrôle qui s'abstient partout est un contrôle absent
(`standards/04-fiabilite-des-controles.md` §1).
"""

import os

import pytest


def weasyprint_disponible() -> bool:
    try:
        import weasyprint  # noqa: F401
    except Exception:
        return False
    return True


DISPONIBLE = weasyprint_disponible()
EN_INTEGRATION_CONTINUE = os.getenv("CI", "").lower() in ("1", "true", "yes")

besoin_weasyprint = pytest.mark.skipif(
    not DISPONIBLE,
    reason="WeasyPrint absent (bibliothèques système) — voir test_weasyprint_present_en_ci",
)


def exiger_weasyprint_en_ci() -> None:
    """Le test de portée, écrit une fois et appelé par chaque fichier concerné."""
    if not EN_INTEGRATION_CONTINUE:
        pytest.skip("hors intégration continue — abstention légitime")
    assert DISPONIBLE, (
        "WeasyPrint indisponible en intégration continue : le rendu des documents "
        "n'est vérifié nulle part. Installer libpango/libcairo dans le job."
    )
