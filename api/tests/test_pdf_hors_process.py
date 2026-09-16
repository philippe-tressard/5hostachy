"""Le rendu PDF sort-il vraiment du process de l'API ? — et y reste-t-il dehors ?

POURQUOI CE TEST (16/09/2026) :

Le rendu des documents imprimables a été isolé dans un process `spawn`, pour que
WeasyPrint ne puisse plus emporter l'API en plantant ou en épuisant la mémoire du
RPi, et pour supprimer la pointe de latence qu'il impose aux requêtes
concurrentes (mesurée : `/health` à 122 ms pendant un rendu, contre 3,3 ms après
— le détail est dans `app/utils/pdf_rendu.py`).

⚠️ Ce module ne corrige aucun « figeage » du site : la première version de ce
fichier l'affirmait, et la mesure l'a démenti. Ce qui est vérifié ici est plus
modeste et plus vrai : le rendu a lieu ailleurs, et il y reste.

Trois propriétés, dont aucune n'est visible à la lecture du code appelant et que
toutes trois peuvent être défaites par une modification d'apparence anodine :

1. **le rendu a lieu ailleurs** — sinon l'isolation n'existe plus, en silence ;
2. **l'enfant est `spawn` et pas `fork`** — un enfant forké hérite des
   descripteurs de `app.db` et peut `unlink` le WAL sous l'API vivante (la règle
   d'or, et l'incident du 17/07/2026) ;
3. **le journal de l'enfant remonte** — sans quoi `test_documents_pdf.py`
   ::`test_la_fiche_avec_ses_icones_se_rend_en_pdf` lirait un `caplog` vide et
   deviendrait vert pour toujours. Ce test-ci protège donc un autre test.

⚠️ **La porte, elle, est gardée ailleurs** — et il a fallu casser ce contrôle-là
pour s'en apercevoir : `test_weasyprint_appel_unique.py` vérifiait DÉJÀ que
WeasyPrint n'est appelé qu'à un seul endroit, et il a échoué au premier rejeu de
la CI parce que l'appel avait déménagé. La première version de ce fichier en
avait écrit un second, par ignorance du premier. Il n'en reste qu'un : celui qui
existait, mis à jour, et qui porte maintenant les deux raisons de tenir la porte
fermée (la dérogation de sécurité et l'isolation).
"""
import logging
import os
import re

import pytest

from tests.aides_pdf import besoin_weasyprint, exiger_weasyprint_en_ci

#: Un document minimal : ce qu'on mesure ici est l'isolation, pas la mise en page.
HTML_MINIMAL = "<html><body><h1>Essai</h1><p>Contenu.</p></body></html>"

def test_weasyprint_present_en_ci():
    """La portée du fichier : s'abstenir partout serait n'avoir aucun contrôle."""
    exiger_weasyprint_en_ci()


@besoin_weasyprint
def test_le_rendu_se_fait_dans_un_autre_process(caplog):
    """La propriété sur laquelle tout le reste repose : ce n'est pas nous qui rendons.

    Le témoin est la ligne que l'enfant émet avant de rendre, rejouée ici par le
    parent. Comparer les PID est direct et déterministe — là où un test de
    concurrence (« un thread avance-t-il pendant le rendu ? ») dépendrait de la
    charge de la machine et finirait désarmé pour cause d'instabilité. C'est
    d'ailleurs par une mesure de ce genre qu'on a découvert que le rendu en
    process ne bloquait pas le site : elle informe, elle ne verrouille pas.
    """
    from app.utils.pdf_theme import html_to_pdf

    with caplog.at_level(logging.INFO, logger="hostachy.pdf"):
        contenu = html_to_pdf(HTML_MINIMAL)

    assert contenu[:5] == b"%PDF-", "le rendu ne produit plus un PDF"

    temoins = [r.getMessage() for r in caplog.records if r.name == "hostachy.pdf"]
    assert temoins, (
        "aucun témoin de rendu : soit l'enfant ne l'émet plus, soit le journal "
        "ne remonte plus jusqu'ici — dans les deux cas ce fichier ne mesure plus rien"
    )
    trouve = re.search(r"process (\d+)", temoins[0])
    assert trouve, f"témoin illisible : {temoins[0]!r}"
    assert int(trouve.group(1)) != os.getpid(), (
        "le PDF a été rendu DANS le process de l'API : l'isolation a disparu, "
        "un plantage de WeasyPrint emporte de nouveau l'API"
    )


@besoin_weasyprint
def test_l_enfant_n_herite_pas_de_la_base_donc_ce_n_est_pas_un_fork(caplog):
    """`spawn` et non `fork` — vérifié par ce que l'enfant a en mémoire.

    On charge délibérément `app.database` **ici**, dans le parent, avant de
    rendre. Un enfant forké hériterait de tout `sys.modules`, donc de ce module
    et des descripteurs de `app.db` qu'il tient. Un enfant `spawn` démarre d'un
    interpréteur neuf et ne l'a pas.

    C'est la formulation comportementale de la règle d'or : on n'affirme pas que
    le code demande `spawn`, on constate que l'enfant n'a pas la base.
    """
    import app.database  # noqa: F401 — l'import EST le dispositif du test

    from app.utils.pdf_theme import html_to_pdf

    with caplog.at_level(logging.INFO, logger="hostachy.pdf"):
        html_to_pdf(HTML_MINIMAL)

    temoins = [r.getMessage() for r in caplog.records if r.name == "hostachy.pdf"]
    assert temoins, "témoin de rendu absent — voir le test précédent"
    assert "base chargée : False" in temoins[0], (
        "le process de rendu a la base en mémoire : c'est un fork, et il tient "
        f"donc les descripteurs de app.db ({temoins[0]!r})"
    )


@besoin_weasyprint
def test_le_journal_de_weasyprint_remonte_au_parent(caplog):
    """Sans ce transfert, un autre test deviendrait vert pour toujours.

    `test_la_fiche_avec_ses_icones_se_rend_en_pdf` conclut « WeasyPrint ne s'est
    pas plaint du document » en lisant `caplog`. Le rendu ayant lieu ailleurs,
    un `caplog` vide s'y lirait comme une absence de plainte — soit exactement
    le faux vert que ce dépôt passe son temps à débusquer.

    On provoque donc une plainte connue : `box-shadow` n'est pas supportée, et
    WeasyPrint le dit à chaque rendu depuis toujours.
    """
    from app.utils.pdf_theme import html_to_pdf

    html = (
        "<html><head><style>p { box-shadow: 0 0 2px #000; }</style></head>"
        "<body><p>Contenu.</p></body></html>"
    )
    with caplog.at_level(logging.WARNING, logger="weasyprint"):
        html_to_pdf(html)

    plaintes = [r.getMessage() for r in caplog.records if r.name.startswith("weasyprint")]
    assert any("box-shadow" in p for p in plaintes), (
        "la plainte de WeasyPrint n'est pas remontée du process de rendu : tout "
        f"contrôle qui lit caplog est devenu aveugle (reçu : {plaintes})"
    )


@besoin_weasyprint
def test_un_rendu_trop_long_est_abandonne_proprement():
    """Le chemin d'erreur, exercé — et non seulement écrit.

    Un délai d'une milliseconde ne peut pas être tenu : démarrer un interpréteur
    `spawn` en demande plusieurs centaines. On vérifie que l'attente s'arrête,
    qu'elle le dit franchement, et qu'elle ne rend surtout pas un document
    partiel.
    """
    from app.utils.pdf_rendu import RenduPdfImpossible, rendre_pdf

    with pytest.raises(RenduPdfImpossible) as echec:
        rendre_pdf(HTML_MINIMAL, delai_s=0.001)

    assert "abandonné" in str(echec.value)
