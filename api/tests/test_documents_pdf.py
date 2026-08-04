"""Les documents imprimables se rendent-ils encore ? — le contrôle qui manquait.

POURQUOI CE TEST (04/08/2026) :

Une PR Dependabot proposait `weasyprint` 63.1 → **69.0** (six versions majeures) et
`Pillow` 11 → 12, groupés avec un correctif de sécurité. Elle était **verte**.

Elle ne pouvait pas être autre chose : `pdf_theme.html_to_pdf()` importe WeasyPrint
de façon différée (`from weasyprint import HTML` à l'intérieur de la fonction), donc
**aucun test de la suite ne l'exerçait jamais**. Le vert prouvait que les paquets
s'installent — jamais qu'un PDF sort, ni qu'il sort correct.

C'est le motif exact du bug du 26/07/2026 : le mois affiché en anglais sur la fiche
arrivant, trouvé **à l'œil sur un document**, parce qu'aucun contrôle ne regardait le
rendu. On avait alors ajouté un test qui interdit `%B` dans le code ; il ne dit
toujours rien de ce qui sort de la moulinette.

CE QUE CE TEST GARANTIT : les deux documents réellement produits par l'application —
fiche arrivant et annonce de hall — se rendent en PDF valide, non vide, sans lever.

⚠️ WeasyPrint a besoin de bibliothèques système (pango, cairo) absentes d'un poste
Windows. Le test s'y abstient donc — mais il **échoue** si WeasyPrint manque en
intégration continue, où le job installe ce qu'il faut. Un contrôle qui s'abstient
partout serait un contrôle absent : cf. standards/04 §1, un contrôle qui ne peut pas
s'exécuter rend INCONNU, jamais OK.
"""
import os

import pytest


def _weasyprint_disponible() -> bool:
    try:
        import weasyprint  # noqa: F401
    except Exception:
        return False
    return True


DISPONIBLE = _weasyprint_disponible()
EN_INTEGRATION_CONTINUE = os.getenv("CI", "").lower() in ("1", "true", "yes")

besoin_weasyprint = pytest.mark.skipif(
    not DISPONIBLE,
    reason="WeasyPrint absent (bibliothèques système) — voir test_weasyprint_present_en_ci",
)


def test_weasyprint_present_en_ci():
    """Sans lui, tous les tests de ce fichier s'abstiendraient — donc ne diraient rien.

    C'est la portée du contrôle qui est vérifiée ici : sur un poste de développement
    Windows, l'abstention est légitime ; en intégration continue, elle signifierait
    que le job n'installe pas les bibliothèques système et que le rendu n'est
    contrôlé NULLE PART.
    """
    if not EN_INTEGRATION_CONTINUE:
        pytest.skip("hors intégration continue — abstention légitime")
    assert DISPONIBLE, (
        "WeasyPrint indisponible en intégration continue : le rendu des documents "
        "n'est vérifié nulle part. Installer libpango/libcairo dans le job."
    )


@besoin_weasyprint
def test_la_fiche_arrivant_se_rend_en_pdf():
    """Le document remis à un nouvel arrivant — celui du bug du 26/07."""
    from app.utils.fiche_arrivant import generer_fiche_arrivant
    from app.utils.pdf_theme import html_to_pdf

    html = generer_fiche_arrivant(
        cs_data={"membres": [], "titre": "Conseil syndical"},
        syndic_data={"nom": "Syndic Test", "telephone": "0102030405"},
        site_url="5hostachy.fr",
        whatsapp_url=None,
        annee=2026,
    )
    assert html.strip().startswith("<"), "le générateur ne rend plus du HTML"

    contenu = html_to_pdf(html)
    assert contenu[:5] == b"%PDF-", "la sortie n'est pas un PDF"
    assert len(contenu) > 5_000, (
        f"PDF suspicieusement petit ({len(contenu)} octets) — rendu probablement vide"
    )


@besoin_weasyprint
def test_l_annonce_de_hall_se_rend_en_pdf():
    """L'affiche apposée dans le hall — l'autre document imprimable du projet."""
    from datetime import date

    from app.utils.annonce_hall import construire_html
    from app.utils.pdf_theme import html_to_pdf

    html = construire_html(
        titre="Coupure d'eau programmée",
        message_html="<p>L'eau sera coupée <strong>mardi</strong> de 9h à 12h.</p>",
        perimetre_label="Bâtiment 1",
        format_effectif="A4",
        site_nom="5Hostachy",
        site_url="5hostachy.fr",
        images=None,
        date_affichage=date(2026, 8, 4),
    )
    contenu = html_to_pdf(html)
    assert contenu[:5] == b"%PDF-"
    assert len(contenu) > 5_000


@besoin_weasyprint
def test_le_theme_commun_rend_un_pdf_minimal():
    """`html_to_pdf` seul — isole une rupture du moteur d'une rupture d'un document.

    Si ce test tombe alors que les deux précédents tombent aussi, la cause est le
    moteur. S'il tient seul, la cause est dans le document. Distinguer les deux
    évite une heure de recherche au mauvais endroit.
    """
    from app.utils.pdf_theme import html_to_pdf

    contenu = html_to_pdf("<html><body><h1>Essai</h1><p>Contenu.</p></body></html>")
    assert contenu[:5] == b"%PDF-"
