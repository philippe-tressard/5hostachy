"""Les limites d'un usage de l'assistant IA — appels par mois, par heure et par
personne, premier essai (04/10/2026).

Le plafond mensuel se saisissait en jetons, un chiffre que personne ne savait
estimer. Il compte désormais des APPELS, et le premier essai — le premier appel
réussi avec le modèle et l'effort enregistrés — chiffre ce que la limite laisse
dépenser. Ces tests tiennent les promesses de `utils/llm_limites` :

1. **une limite atteinte refuse AVANT l'envoi** — rien n'est facturé ;
2. **le quota horaire vaut par personne**, et pas pour l'automatique ;
3. **le premier essai se périme** quand le modèle ou l'effort change, et le
   test de connexion n'en est jamais un ;
4. **aucun appelant n'oublie qui fait le geste** — sans quoi le quota horaire
   s'éteindrait pour lui sans un mot.
"""

from __future__ import annotations

import ast
import asyncio
import json
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.models.core import ConfigSite
from app.models.ia import AppelIA
from app.utils import horloge, llm_journal, llm_limites
from app.utils import llm
from app.utils.llm import RefusLimite, config_llm, demander
from app.utils.llm_limites import FENETRE_HEURE_S, prendre_place, premier_essai, suivi
from tests.aides_sources import modules_app

USAGE = "synthese_contrat"

OK = {
    "choices": [{"message": {"content": "Synthèse."}}],
    "usage": {"prompt_tokens": 1000, "completion_tokens": 200},
}


@pytest.fixture(autouse=True)
def _heure_vierge():
    """Le compteur horaire vit dans le processus : chaque test part de zéro."""
    llm_limites.oublier_les_places()
    yield
    llm_limites.oublier_les_places()


@pytest.fixture()
def session_ia(session):
    for cle, valeur in {
        "llm_actif": "1",
        "llm_fournisseur": "openai",
        "llm_api_key": "sk-x",
        f"llm_{USAGE}_actif": "1",
        f"llm_{USAGE}_modele": "gpt-4o-mini",
        f"llm_{USAGE}_effort": "faible",
    }.items():
        session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()
    return session


def _poser(session, champ: str, valeur: str) -> None:
    cle = f"llm_{USAGE}_{champ}"
    ligne = session.get(ConfigSite, cle)
    if ligne:
        ligne.valeur = valeur
    else:
        ligne = ConfigSite(cle=cle, valeur=valeur)
    session.add(ligne)
    session.commit()


class _Reponse:
    status_code = 200
    text = ""

    def __init__(self, charge):
        self._charge = charge

    def json(self):
        return self._charge


def _brancher(monkeypatch, charge=OK) -> list:
    """Un faux client HTTP ; rend la liste des requêtes réellement envoyées."""
    import httpx

    envoyees: list = []

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            envoyees.append(k.get("json"))
            return _Reponse(charge)

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return envoyees


def _appeler(session, demandeur=None):
    return asyncio.run(demander(session, usage=USAGE, message="contrat", demandeur=demandeur))


def _statuts(session) -> list[str]:
    with Session(session.get_bind()) as s:
        return sorted(a.statut for a in s.exec(select(AppelIA)).all())


def _succes(session, **champs) -> None:
    session.add(AppelIA(usage=USAGE, fournisseur="openai", modele="m", **champs))
    session.commit()


#  ── 1. La limite du mois ────────────────────────────────────────────────────


def test_la_limite_du_mois_refuse_sans_appeler_le_fournisseur(monkeypatch, session_ia):
    envoyees = _brancher(monkeypatch)
    _poser(session_ia, "appels_mois", "2")
    _succes(session_ia)
    _succes(session_ia)
    with pytest.raises(RefusLimite, match="Limite du mois atteinte"):
        _appeler(session_ia)
    assert envoyees == [], "le fournisseur a été appelé malgré la limite"
    assert _statuts(session_ia) == ["plafond", "succes", "succes"]


def test_le_mois_ne_compte_que_ses_appels_reussis(monkeypatch, session_ia):
    _brancher(monkeypatch)
    _poser(session_ia, "appels_mois", "1")
    _succes(session_ia, statut="erreur")
    _succes(session_ia, cree_le=llm_journal.debut_du_mois(horloge.maintenant()) - timedelta(days=1))
    _appeler(session_ia)
    with pytest.raises(RefusLimite):
        _appeler(session_ia)


def test_sans_limite_rien_n_est_refuse(monkeypatch, session_ia):
    _brancher(monkeypatch)
    for _ in range(3):
        _succes(session_ia)
    _appeler(session_ia, demandeur=7)


#  ── 2. Le quota par heure et par personne ───────────────────────────────────


def test_le_quota_de_l_heure_vaut_par_personne(monkeypatch, session_ia):
    envoyees = _brancher(monkeypatch)
    _poser(session_ia, "appels_heure", "2")
    _appeler(session_ia, demandeur=7)
    _appeler(session_ia, demandeur=7)
    with pytest.raises(RefusLimite, match="réessayez dans"):
        _appeler(session_ia, demandeur=7)
    _appeler(session_ia, demandeur=8)
    assert len(envoyees) == 3
    assert _statuts(session_ia) == ["quota", "succes", "succes", "succes"]


def test_l_automatique_n_a_pas_de_quota_horaire(monkeypatch, session_ia):
    _brancher(monkeypatch)
    _poser(session_ia, "appels_heure", "1")
    for _ in range(3):
        _appeler(session_ia, demandeur=None)


def test_un_refus_du_mois_ne_prend_pas_de_place_dans_l_heure(monkeypatch, session_ia):
    _brancher(monkeypatch)
    _poser(session_ia, "appels_mois", "1")
    _poser(session_ia, "appels_heure", "1")
    _succes(session_ia)
    with pytest.raises(RefusLimite, match="Limite du mois"):
        _appeler(session_ia, demandeur=7)
    _poser(session_ia, "appels_mois", "")
    _appeler(session_ia, demandeur=7)


def test_l_heure_est_glissante():
    assert prendre_place("u", 1, 2, instant=0) is None
    assert prendre_place("u", 1, 2, instant=600) is None
    #  Pleine : la plus ancienne se libère dans 3 600 − 1 200 s.
    assert prendre_place("u", 1, 2, instant=1200) == 2400
    assert prendre_place("u", 1, 2, instant=FENETRE_HEURE_S) is None


#  ── 3. Le premier essai ─────────────────────────────────────────────────────


def _reference(session) -> dict:
    return premier_essai(session, USAGE, config_llm(session, USAGE))


def test_le_premier_appel_est_l_etalon_et_le_second_ne_le_remplace_pas(monkeypatch, session_ia):
    _brancher(monkeypatch)
    _appeler(session_ia)
    _brancher(monkeypatch, {**OK, "usage": {"prompt_tokens": 9, "completion_tokens": 9}})
    _appeler(session_ia)
    ref = _reference(session_ia)
    assert (ref["modele"], ref["effort"]) == ("gpt-4o-mini", "Faible")
    assert (ref["jetons_entree"], ref["jetons_sortie"]) == (1000, 200)
    assert ref["cout_usd"] is None, "sans tarif, le coût se tait"


@pytest.mark.parametrize("champ, valeur", [("modele", "gpt-5"), ("effort", "eleve")])
def test_changer_de_modele_ou_d_effort_perime_l_etalon(monkeypatch, session_ia, champ, valeur):
    _brancher(monkeypatch)
    _appeler(session_ia)
    _poser(session_ia, champ, valeur)
    assert _reference(session_ia) is None
    _brancher(monkeypatch, {**OK, "usage": {"prompt_tokens": 50, "completion_tokens": 5}})
    _appeler(session_ia)
    assert _reference(session_ia)["jetons_entree"] == 50


def test_le_test_de_connexion_n_est_pas_un_essai(monkeypatch, session_ia):
    _brancher(monkeypatch)
    asyncio.run(llm.tester(session_ia, USAGE, demandeur=1))
    assert _reference(session_ia) is None


def test_le_suivi_chiffre_l_essai_au_tarif_saisi(monkeypatch, session_ia):
    _brancher(monkeypatch)
    _poser(session_ia, "appels_mois", "50")
    _poser(session_ia, "prix_entree", "2")
    _poser(session_ia, "prix_sortie", "10")
    _appeler(session_ia)
    (ligne,) = [x for x in suivi(session_ia) if x["usage"] == USAGE]
    assert (ligne["appels_mois"], ligne["appels"]) == (50, 1)
    #  1 000 × 2 $ + 200 × 10 $ par million = 0,004 $.
    assert ligne["premier_essai"]["cout_usd"] == "0.0040"


def test_un_etalon_illisible_ne_casse_rien(session_ia):
    _poser(session_ia, "reference", "{pas du json")
    assert _reference(session_ia) is None
    _poser(session_ia, "reference", json.dumps(["liste"]))
    assert _reference(session_ia) is None


#  ── 4. Aucun appelant n'oublie qui fait le geste ────────────────────────────


def test_tout_appel_a_demander_dit_qui_le_fait():
    """`demandeur` est sans défaut : l'oublier lève à l'exécution. Ce relevé le
    voit AVANT, sur le code — un faux `demander` de test, qui accepte tout,
    masquerait l'oubli."""
    appels, fautes = 0, []
    for m in modules_app():
        for n in ast.walk(m.arbre):
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "demander":
                appels += 1
                if "demandeur" not in {k.arg for k in n.keywords}:
                    fautes.append(f"{m.rel}:{n.lineno}")
    assert appels >= 6, "le relevé ne trouve plus les appels — il ne mesure rien"
    assert not fautes, "demander() appelé sans demandeur :\n  " + "\n  ".join(fautes)
