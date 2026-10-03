"""La synthèse d'une affaire close : la réponse de l'assistant et les métriques (#1643).

Deux règles pures, sans base :

- `format.lire_reponse` relit le JSON à trois clés — `synthese` ne peut pas
  manquer, `difficultes` et `amelioration` peuvent être vides ;
- `metriques.calculer` mesure en jours ouvrés (heures de Paris) : étapes, la
  plus longue, Suites, relances, réaction, première réponse du syndic, semaines
  muettes, chronologie, réouverture ; puis l'exercice et la moyenne.

Les dates sont en janvier 2026 (UTC + 1) : 08:00 UTC est 9 h à Paris.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from app.utils.description_format import ReponseIllisible
from app.utils.synthese_affaire.format import consigne_complete, lire_reponse
from app.utils.synthese_affaire.metriques import (
    CLOSE_AVANT_REOUVERTURE,
    Fait,
    bornes_exercice,
    calculer,
    moyenne,
)


def test_lire_reponse_a_trois_cles():
    texte = '```json\n{"synthese": "<p>Récit</p>", "difficultes": "", "amelioration": null}\n```'
    assert lire_reponse(texte) == {
        "synthese": "<p>Récit</p>",
        "difficultes": "",
        "amelioration": "",
    }


@pytest.mark.parametrize(
    "texte",
    [
        "Voici la synthèse, en prose.",
        '{"difficultes": "x"}',
        '{"synthese": "   "}',
        '{"synthese": "ok", "amelioration": 3}',
    ],
)
def test_lire_reponse_refuse(texte):
    with pytest.raises(ReponseIllisible):
        lire_reponse(texte)


def test_le_complement_est_ajoute_au_prompt_jamais_a_sa_place():
    consigne = consigne_complete("PROMPT", "Insister sur le prestataire")
    assert consigne.startswith("PROMPT")
    assert "Insister sur le prestataire" in consigne
    assert consigne.rstrip().endswith("}")  # le format en dernier
    assert "complémentaire" not in consigne_complete("PROMPT", "  ")


def _t(jour: int, heure: int = 8) -> datetime:
    return datetime(2026, 1, jour, heure)


FIL = [
    Fait(_t(7), "etat", "ouvert", "en_cours"),
    Fait(_t(12), "etat", "en_cours", "en_ag"),
    Fait(_t(13, 9), "relance"),
    Fait(_t(14, 12), "commentaire", syndic=True),
    Fait(_t(28), "etat", "en_ag", "résolu"),
]


def test_les_metriques_d_une_affaire_passee_par_l_ag():
    met = calculer(cree_le=_t(5), cloture_le=_t(28), issue="résolu", faits=FIL)
    jours = {e["statut"]: e["jours"] for e in met["etapes"]}
    assert jours == {"ouvert": 2.0, "en_cours": 3.0, "en_ag": 12.0}
    assert met["duree_totale"] == 17.0
    assert met["etape_plus_longue"] == "en_ag"
    assert met["suites"] == 4
    assert met["relances"] == 1
    assert met["reaction_relance"] == 1.5
    assert met["premiere_reponse_syndic"] == 7.5
    assert met["semaines"] == [1, 2, 0, 1]
    assert met["semaines_muettes"] == 1
    assert met["reouvertures"] == 0
    types = [j["type"] for j in met["chronologie"]]
    assert types == ["creation", "etat", "etat", "relance", "etat"]
    assert met["chronologie"][1]["ecart"] == 2.0
    assert met["comparaison"] is None


def test_l_ordre_des_etapes_est_celui_du_kanban():
    met = calculer(cree_le=_t(5), cloture_le=_t(28), issue="résolu", faits=FIL)
    assert [e["statut"] for e in met["etapes"]] == ["ouvert", "en_ag", "en_cours"]


def test_l_ag_n_apparait_que_si_l_affaire_y_est_passee():
    fil = [Fait(_t(6), "etat", "ouvert", "en_cours"), Fait(_t(9), "etat", "en_cours", "annulé")]
    met = calculer(cree_le=_t(5), cloture_le=_t(9), issue="annulé", faits=fil)
    assert [e["statut"] for e in met["etapes"]] == ["ouvert", "en_cours"]
    assert met["premiere_reponse_syndic"] is None
    assert met["reaction_relance"] is None


def test_une_cloture_sans_transition_tracee_termine_quand_meme_la_frise():
    """Un état corrigé par la fiche n'écrit pas de transition : la clôture ferme."""
    met = calculer(cree_le=_t(5), cloture_le=_t(7), issue="résolu", faits=[])
    assert met["etapes"] == [{"statut": "ouvert", "jours": 2.0}]
    assert met["chronologie"][-1] | {"quand": None} == {
        "quand": None,
        "type": "etat",
        "statut": "résolu",
        "ecart": 2.0,
    }


def test_une_reouverture_couvre_toute_la_vie():
    fil = [
        Fait(_t(6), "etat", "ouvert", "résolu"),
        Fait(_t(8), "etat", "résolu", "en_cours"),
        Fait(_t(9), "etat", "en_cours", "résolu"),
    ]
    met = calculer(cree_le=_t(5), cloture_le=_t(9), issue="résolu", faits=fil)
    jours = {e["statut"]: e["jours"] for e in met["etapes"]}
    assert jours == {"ouvert": 1.0, "en_cours": 1.0, CLOSE_AVANT_REOUVERTURE: 2.0}
    assert met["etape_plus_longue"] == "ouvert"
    assert met["reouvertures"] == 1
    assert met["duree_totale"] == 4.0


def test_l_exercice_comptable():
    assert bornes_exercice(date(2026, 1, 28), None) == (date(2026, 1, 1), date(2027, 1, 1), "2026")
    assert bornes_exercice(date(2026, 1, 28), 7) == (
        date(2025, 7, 1),
        date(2026, 7, 1),
        "2025-2026",
    )
    assert bornes_exercice(date(2026, 7, 1), 7)[2] == "2026-2027"


def test_la_moyenne_est_masquee_sous_trois_affaires():
    mesures = [
        {"duree_totale": 10.0, "premiere_reponse_syndic": 2.0, "relances": 1, "suites": 4},
        {"duree_totale": 20.0, "premiere_reponse_syndic": None, "relances": 0, "suites": 6},
    ]
    assert moyenne(mesures, "panne", "2026") is None
    mesures.append(
        {"duree_totale": 6.0, "premiere_reponse_syndic": 3.0, "relances": 2, "suites": 5}
    )
    assert moyenne(mesures, "panne", "2026") == {
        "nombre": 3,
        "categorie": "panne",
        "exercice": "2026",
        "duree_totale": 12.0,
        "premiere_reponse_syndic": 2.5,
        "relances": 1.0,
        "suites": 5.0,
    }
