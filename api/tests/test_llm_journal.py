"""Ce que coûte l'assistant IA : le journal, le plafond, la consommation (#1383).

L'assistant a un usage AUTOMATIQUE — les réponses du syndic par courriel, toutes
les dix minutes — et rien ne comptait ses appels. Ces tests tiennent les trois
promesses du lot :

1. **chaque appel parti se journalise**, succès comme échec, avec ses jetons ;
2. **un plafond atteint refuse AVANT l'envoi** — le fournisseur n'est pas
   appelé, donc rien n'est facturé ;
3. **le coût se tait sans tarif** : `None`, jamais 0, qui se lirait « gratuit ».

Et deux garde-fous de forme : le journal ne s'écrit qu'à UN endroit, et aucun
module n'appelle un fournisseur sans passer par `demander`.
"""

from __future__ import annotations

import asyncio
import pathlib
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.core import ConfigSite
from app.models.ia import AppelIA
from app.utils import horloge, llm_journal
from app.utils.llm import ErreurLLM, demander
from app.utils.llm_journal import (
    _cout_centimes,
    consommation,
    jetons_de,
    limite_conservation,
    problemes_ia,
)

USAGE = "synthese_contrat"
APP = pathlib.Path(__file__).resolve().parents[1] / "app"


@pytest.fixture()
def session_ia():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        for cle, valeur in {
            "llm_actif": "1",
            "llm_fournisseur": "openai",
            "llm_api_key": "sk-x",
            f"llm_{USAGE}_actif": "1",
            f"llm_{USAGE}_modele": "gpt-4o-mini",
        }.items():
            s.add(ConfigSite(cle=cle, valeur=valeur))
        s.commit()
        yield s


class _Reponse:
    def __init__(self, code, charge=None):
        self.status_code = code
        self._charge = charge or {}
        self.text = ""

    def json(self):
        return self._charge


def _brancher(monkeypatch, reponse) -> list:
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
            return reponse

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return envoyees


def _appels(session) -> list[AppelIA]:
    with Session(session.get_bind()) as s:
        return list(s.exec(select(AppelIA)).all())


OK = _Reponse(
    200,
    {
        "choices": [{"message": {"content": "Synthèse."}}],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 300},
    },
)


#  ── Les jetons, dans les deux vocabulaires ──────────────────────────────────


def test_les_jetons_se_lisent_chez_openai_et_chez_anthropic():
    assert jetons_de({"usage": {"prompt_tokens": 10, "completion_tokens": 3}}) == (10, 3)
    assert jetons_de({"usage": {"input_tokens": 7, "output_tokens": 2}}) == (7, 2)


def test_sans_compteur_les_jetons_sont_INCONNUS_pas_nuls():
    assert jetons_de({}) == (None, None)
    assert jetons_de({"usage": {"prompt_tokens": True}}) == (None, None)
    assert jetons_de("pas un dict") == (None, None)


#  ── 1. Chaque appel parti se journalise ─────────────────────────────────────


def test_un_appel_reussi_est_journalise_avec_ses_jetons(monkeypatch, session_ia):
    _brancher(monkeypatch, OK)
    rep = asyncio.run(demander(session_ia, usage=USAGE, message="contrat"))
    assert rep.texte == "Synthèse."
    (appel,) = _appels(session_ia)
    assert (appel.usage, appel.modele, appel.statut) == (USAGE, "gpt-4o-mini", "succes")
    assert (appel.jetons_entree, appel.jetons_sortie) == (1200, 300)


def test_un_echec_du_fournisseur_est_journalise_aussi(monkeypatch, session_ia):
    _brancher(monkeypatch, _Reponse(500))
    with pytest.raises(ErreurLLM):
        asyncio.run(demander(session_ia, usage=USAGE, message="contrat"))
    assert [a.statut for a in _appels(session_ia)] == ["erreur"]


def test_un_usage_desactive_n_est_ni_envoye_ni_journalise(monkeypatch, session_ia):
    """Rien n'est parti : rien à compter."""
    envoyees = _brancher(monkeypatch, OK)
    ligne = session_ia.exec(select(ConfigSite).where(ConfigSite.cle == f"llm_{USAGE}_actif")).one()
    ligne.valeur = "0"
    session_ia.commit()
    with pytest.raises(ErreurLLM):
        asyncio.run(demander(session_ia, usage=USAGE, message="contrat"))
    assert envoyees == [] and _appels(session_ia) == []


#  ── 2. Le plafond refuse AVANT l'envoi ──────────────────────────────────────


def test_un_plafond_atteint_refuse_sans_appeler_le_fournisseur(monkeypatch, session_ia):
    envoyees = _brancher(monkeypatch, OK)
    session_ia.add(ConfigSite(cle=f"llm_{USAGE}_plafond_mois", valeur="1000"))
    session_ia.add(
        AppelIA(
            usage=USAGE,
            fournisseur="openai",
            modele="gpt-4o-mini",
            jetons_entree=900,
            jetons_sortie=200,
        )
    )
    session_ia.commit()
    with pytest.raises(ErreurLLM, match="Plafond mensuel atteint"):
        asyncio.run(demander(session_ia, usage=USAGE, message="contrat"))
    assert envoyees == [], "le fournisseur a été appelé malgré le plafond"
    assert sorted(a.statut for a in _appels(session_ia)) == ["plafond", "succes"]


def test_le_plafond_ne_compte_que_le_mois_en_cours(monkeypatch, session_ia):
    _brancher(monkeypatch, OK)
    session_ia.add(ConfigSite(cle=f"llm_{USAGE}_plafond_mois", valeur="1000"))
    session_ia.add(
        AppelIA(
            usage=USAGE,
            fournisseur="openai",
            modele="m",
            jetons_entree=5000,
            cree_le=llm_journal.debut_du_mois(horloge.maintenant()) - timedelta(days=1),
        )
    )
    session_ia.commit()
    asyncio.run(demander(session_ia, usage=USAGE, message="contrat"))


def test_sans_plafond_rien_n_est_refuse(monkeypatch, session_ia):
    _brancher(monkeypatch, OK)
    session_ia.add(AppelIA(usage=USAGE, fournisseur="openai", modele="m", jetons_entree=10_000_000))
    session_ia.commit()
    asyncio.run(demander(session_ia, usage=USAGE, message="contrat"))


#  ── 3. Le coût, et son silence ──────────────────────────────────────────────


def test_le_cout_se_calcule_sur_le_total_du_mois():
    #  3 000 jetons à 3 € le million : 0,9 centime — arrondi par appel, il
    #  disparaîtrait ; sur le total de dix appels, il compte.
    assert _cout_centimes(30_000, 0, 300, 0) == 9


def test_sans_tarif_le_cout_est_absent_jamais_nul():
    assert _cout_centimes(30_000, 5_000, 0, 0) is None


def test_la_consommation_regroupe_par_mois_usage_et_modele(session_ia):
    for statut in ("succes", "succes", "erreur", "plafond"):
        session_ia.add(
            AppelIA(
                usage=USAGE,
                fournisseur="openai",
                modele="gpt-4o-mini",
                statut=statut,
                jetons_entree=1000 if statut == "succes" else None,
                jetons_sortie=500 if statut == "succes" else None,
            )
        )
    session_ia.add(ConfigSite(cle=f"llm_{USAGE}_prix_entree", valeur="1500"))
    session_ia.add(ConfigSite(cle=f"llm_{USAGE}_prix_sortie", valeur="6000"))
    session_ia.commit()
    donnees = consommation(session_ia)
    (mois,) = donnees["mois"]
    (ligne,) = mois["usages"]
    assert (ligne["appels"], ligne["erreurs"], ligne["refus"]) == (4, 1, 1)
    assert (ligne["jetons_entree"], ligne["jetons_sortie"]) == (2000, 1000)
    #  2 000 × 15 € + 1 000 × 60 € par million = 0,09 € → 9 centimes.
    assert ligne["cout_centimes"] == 9


#  ── Le courriel de 06:00 et la conservation ─────────────────────────────────


def test_un_refus_des_dernieres_24_h_est_signale_une_fois_par_usage(session_ia):
    for heures in (1, 2, 30):
        session_ia.add(
            AppelIA(
                usage=USAGE,
                fournisseur="openai",
                modele="m",
                statut="plafond",
                cree_le=horloge.maintenant() - timedelta(hours=heures),
            )
        )
    session_ia.commit()
    (ligne,) = problemes_ia(session_ia)
    assert "refusé 2 fois" in ligne


def test_sans_refus_le_courriel_ne_dit_rien(session_ia):
    session_ia.add(AppelIA(usage=USAGE, fournisseur="openai", modele="m"))
    session_ia.commit()
    assert problemes_ia(session_ia) == []


def test_treize_mois_de_detail():
    assert limite_conservation(datetime(2026, 9, 27, 15, 0)) == datetime(2025, 9, 1)
    assert limite_conservation(datetime(2026, 1, 1, 0, 0)) == datetime(2025, 1, 1)


#  ── Les garde-fous de forme ─────────────────────────────────────────────────


def _sources():
    return {p: p.read_text(encoding="utf-8") for p in APP.rglob("*.py")}


def test_le_journal_ne_s_ecrit_qu_a_un_endroit():
    """`demander` journalise ; un second écrivain compterait deux fois."""
    ecrivains = sorted(
        p.relative_to(APP).as_posix()
        for p, src in _sources().items()
        if "journaliser(" in src or "AppelIA(" in src
    )
    assert ecrivains == ["models/ia.py", "utils/llm.py", "utils/llm_journal.py"], ecrivains


def test_aucun_module_n_appelle_un_fournisseur_sans_passer_par_demander():
    """Un appel qui contournerait `demander` ne serait ni compté ni plafonné."""
    appelants = sorted(
        p.relative_to(APP).as_posix() for p, src in _sources().items() if ".url(cfg.modele" in src
    )
    assert appelants == ["utils/llm.py"], appelants
