"""« Pièces jointes disponibles ci-dessous » ne doit pas mentir.

Extrait de `test_pieces_jointes.py` le 18/08/2026 : ce fichier franchissait 500
lignes et le garde-fou de modularité a refusé qu'il grossisse pour couvrir les
envois du calendrier. Le découpage suit le sujet — ce test-ci ne parle ni du nom
d'un fichier, ni du filtre d'écriture : il vérifie qu'un e-mail **annonce ce
qu'il transporte**.

Le drapeau `fichiers` doit être calculé sur la liste RÉELLEMENT attachée, jamais
sur l'intention. Le défaut d'origine : un courriel annonçait des pièces jointes
en se fiant à `body.fichiers_urls`, alors que l'attachement, lui, partait de
`chemins_locaux(...)` — une URL externe ou un fichier hors du répertoire des
téléversements disparaissait en route, et le lecteur cherchait une pièce absente.
"""
import re

import pytest

from tests.test_pieces_jointes import RACINE

#: Noms des variables qui contiennent des chemins RÉSOLUS (sortis de
#: `chemins_locaux`), donc réellement joignables à un e-mail.
_LISTES_RESOLUES = {"pieces_jointes", "photo_paths", "all_attachments", "attachments"}

_DRAPEAU_FICHIERS = re.compile(r'"fichiers":\s*bool\(([A-Za-z_][\w.]*)\)')


@pytest.mark.parametrize(
    "chemin",
    #  ⚠️ Le calendrier a déménagé le 18/08/2026 — perdre sa cible bruyamment est
    #  la bonne façon de la perdre.
    ["api/app/routers/tickets/courriels.py", "api/app/routers/publications/courriels.py",
     "api/app/routers/calendrier_courriels.py"],
)
def test_le_drapeau_fichiers_decrit_ce_qui_est_vraiment_joint(chemin):
    """« Pièces jointes disponibles ci-dessous » ne doit pas mentir.

    Les modèles `ticket_syndic`, `publication_syndic` et
    `calendrier_evenement_cree` affichent cette phrase derrière
    `{% if fichiers %}`. Deux points d'appel calculaient le drapeau sur
    l'INTENTION (`bool(body.fichiers_urls)`) au lieu de la liste réellement
    transmise : le commentaire de ticket envoyé au syndic annonçait des pièces
    jointes sans en attacher aucune, et l'actualité faisait l'inverse — elle les
    attachait sans les annoncer. Le drapeau se calcule sur la liste résolue,
    jamais sur la requête.
    """
    source = (RACINE / chemin).read_text(encoding="utf-8")
    references = _DRAPEAU_FICHIERS.findall(source)
    assert references, f"aucun drapeau `fichiers` trouvé dans {chemin}"
    for ref in references:
        assert ref in _LISTES_RESOLUES, (
            f'{chemin} : "fichiers" calculé sur `{ref}`, qui n\'est pas une liste '
            f"de chemins résolus ({sorted(_LISTES_RESOLUES)})"
        )
