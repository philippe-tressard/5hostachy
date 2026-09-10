"""Le carnet d'entretien — sa seule décision, et son cas zéro.

Le carnet est une **vue** : l'essentiel de son code lit trois tables et les
concatène. Une seule ligne y décide quelque chose — *cette visite est-elle en
retard ?* —, et c'est elle qui est éprouvée ici, sans base ni session.

Le reste est vérifié par ce qui l'entoure : `test_liens_front.py` refuse un lien
vers une route que `pages.ts` ne déclare pas (le préfixe `contrat` a été ajouté
avec ce lot), et `test_types_equipement.py` tient déjà la correspondance entre
`TypeEquipement` et la table des libellés du front.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.utils.carnet_entretien import CATEGORIES_BATI, _concerne, alerte_visite

AUJOURDHUI = date(2026, 9, 10)


def test_aucune_echeance_n_est_pas_un_retard():
    """Un contrat sans visite programmée ne dit rien — il ne dit pas l'inverse."""
    assert alerte_visite(None, AUJOURDHUI) is None


def test_une_echeance_a_venir_ne_crie_pas():
    assert alerte_visite(date(2026, 12, 1), AUJOURDHUI) is None


def test_le_JOUR_MEME_n_est_pas_un_retard():
    """🔴 Le bord qui ferait crier le carnet sur un contrat parfaitement tenu.

    Une visite attendue aujourd'hui peut encore avoir lieu cet après-midi. Un
    `<=` au lieu d'un `<` mettrait en alerte, chaque matin, tous les contrats du
    jour — et une alerte qui crie sur du normal finit ignorée.
    """
    assert alerte_visite(AUJOURDHUI, AUJOURDHUI) is None


def test_un_retard_dit_COMBIEN():
    """Trois jours et deux ans ne demandent pas le même geste."""
    assert alerte_visite(date(2026, 9, 7), AUJOURDHUI) == "visite attendue depuis 3 jours"
    assert alerte_visite(date(2024, 9, 10), AUJOURDHUI) == "visite attendue depuis 730 jours"


def test_le_pluriel_s_accorde():
    """Un jour de retard s'écrit au singulier — la grammaire est calculée ici,
    jamais dans un gabarit, comme pour les modèles d'e-mail."""
    assert alerte_visite(date(2026, 9, 9), AUJOURDHUI) == "visite attendue depuis 1 jour"


def test_les_categories_retenues_parlent_du_BATI():
    """Cas zéro : si le filtre devenait vide ou total, le carnet mentirait.

    Vide, il n'afficherait aucun incident ; total, il y noierait les questions et
    les signalements de bug, que ni un acquéreur ni un syndic n'y cherchent.
    """
    from app.models.tickets import CategorieTicket

    valeurs = {c.value for c in CATEGORIES_BATI}
    assert valeurs == {"panne", "espaces_verts", "sinistre", "etude_travaux"}
    #  Et le filtre EXCLUT bien quelque chose : un ensemble qui contiendrait tout
    #  passerait ce test-ci sans rien filtrer.
    assert CategorieTicket.question not in CATEGORIES_BATI
    assert CategorieTicket.bug not in CATEGORIES_BATI


def test_sans_filtre_il_n_y_a_RIEN_a_filtrer():
    from app.models.prestataires import ContratEntretien

    assert _concerne(ContratEntretien.batiment_id, None) is None


def test_un_batiment_inclut_ce_qui_couvre_TOUTE_la_residence():
    """🔴 Le défaut signalé à l'écran le 10/09/2026 : choisir un bâtiment vidait
    le carnet.

    `batiment_id == 3` seul exclut tout ce qui porte `NULL` — un contrat de
    nettoyage, d'espaces verts ou d'assurance, un événement de périmètre
    « résidence », un ticket sans bâtiment. C'est-à-dire l'essentiel.

    Et c'était faux sur le fond : l'entretien de la résidence entretient AUSSI
    ce bâtiment. Le test lit le SQL produit — un `OR … IS NULL`, jamais une
    égalité seule.
    """
    from app.models.prestataires import ContratEntretien

    sql = str(_concerne(ContratEntretien.batiment_id, 3))
    assert "IS NULL" in sql, f"les portées « résidence entière » sont exclues : {sql}"
    assert " OR " in sql, f"la condition doit être une UNION : {sql}"
    assert "batiment_id" in sql


@pytest.mark.parametrize("prefixe", ["contrat", "ev"])
def test_les_liens_du_carnet_sont_declares(prefixe):
    """Un lien fabriqué à la main échapperait à `test_liens_front`."""
    from app.utils.liens import EMPLACEMENTS

    assert prefixe in EMPLACEMENTS
