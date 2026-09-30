"""Le tarif du modèle d'un usage, cherché chez son fournisseur et enregistré (30/09/2026).

Ce que ce test protège :

1. **Le prix enregistré est un prix en centimes d'EURO entiers**, converti au
   taux de la BCE par le serveur — jamais par le modèle, qui inventerait un taux.
2. **Un prix absurde est refusé**, pas enregistré : un booléen, une chaîne, un
   négatif, un prix par millier pris pour un prix par million, une devise inconnue.
3. **C'est le modèle ENREGISTRÉ qui est cherché** : un modèle affiché mais pas
   enregistré est refusé, pour ne jamais poser sur l'un le prix de l'autre.
4. **Seul ce qui est trouvé s'enregistre** : un prix absent de la grille laisse
   celui de l'administrateur ; deux absents se disent, rien n'est écrit.
5. **Ce qui part** : le fournisseur, l'identifiant du modèle et la grille publique.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import ConfigSite
from app.utils import llm, tarif_sources
from app.utils.description_format import ReponseIllisible
from app.utils.llm import ErreurLLM
from app.utils.tarif_modele import USAGE_TARIF_MODELE, chercher_et_enregistrer, lire_tarif
from app.utils.tarif_sources import Taux, en_centimes_euro, lire_taux_bce

GRILLE = "| Model | Input | Output |\n| Claude Haiku 4.5 | $1 / MTok | $5 / MTok |"
TAUX = Taux(usd_par_eur=Decimal("1.25"), date="2026-09-30")


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        for cle, valeur in {
            "llm_actif": "1",
            "llm_fournisseur": "anthropic",
            "llm_api_key": "cle-de-test",
            f"llm_{USAGE_TARIF_MODELE}_actif": "1",
            f"llm_{USAGE_TARIF_MODELE}_modele": "modele-qui-lit",
            "llm_description_modele": "claude-haiku-4-5-20251001",
            "llm_description_prix_sortie": "999",
        }.items():
            s.add(ConfigSite(cle=cle, valeur=valeur))
        s.commit()
        yield s


@pytest.fixture()
def sources(monkeypatch):
    """Les deux sources, sans réseau : la grille et le taux sont ceux du test."""
    lues: list[str] = []

    async def grille(url):
        lues.append(url)
        return GRILLE

    async def taux():
        return TAUX

    monkeypatch.setattr(tarif_sources, "lire_grille", grille)
    monkeypatch.setattr(tarif_sources, "lire_taux", taux)
    return lues


def _modele(texte: str, recus: list | None = None):
    async def faux(session, *, usage, message, **_):
        if recus is not None:
            recus.append((usage, message))
        return SimpleNamespace(texte=texte)

    return faux


def _valeur(session, cle):
    ligne = session.get(ConfigSite, cle)
    return None if ligne is None else ligne.valeur


# ── 1. Les pièces pures ────────────────────────────────────────────────────


def test_le_taux_se_lit_dans_le_fichier_de_la_bce():
    xml = (
        "<Cube><Cube time='2026-09-30'><Cube currency='USD' rate='1.0812'/>"
        "<Cube currency='JPY' rate='161.2'/></Cube></Cube>"
    )
    assert lire_taux_bce(xml) == Taux(usd_par_eur=Decimal("1.0812"), date="2026-09-30")


@pytest.mark.parametrize("xml", ["", "<Cube time='2026-09-30'/>", "currency='USD' rate='42'"])
def test_un_taux_absent_ou_invraisemblable_est_refuse(xml):
    with pytest.raises(tarif_sources.SourceIndisponible):
        lire_taux_bce(xml)


def test_la_conversion_arrondit_au_centime_en_decimal():
    assert en_centimes_euro(1, "USD", TAUX) == 80
    #  0,20 $ / 1,08 = 0,18518… € : 18,5 centimes arrondis à 19, pas à 18.
    assert en_centimes_euro(0.2, "USD", Taux(Decimal("1.08"), "")) == 19
    assert en_centimes_euro(0.2, "EUR", None) == 20


def test_un_prix_decimal_se_relit_dans_sa_devise():
    lu = lire_tarif(
        '```json\n{"ligne": "gpt-5.6-luna", "devise": "USD", "prix_entree": 0.2, "prix_sortie": 1.2}\n```'
    )
    assert (lu.ligne, lu.devise, lu.prix_entree, lu.prix_sortie) == (
        "gpt-5.6-luna",
        "USD",
        0.2,
        1.2,
    )


# ── 2. Ce qui n'est pas un prix ────────────────────────────────────────────


@pytest.mark.parametrize("valeur", ["true", '"0,20"', "-1", "1500", "[1]"])
def test_un_prix_qui_n_en_est_pas_un_est_refuse(valeur):
    with pytest.raises(ReponseIllisible):
        lire_tarif(f'{{"ligne": "x", "prix_entree": {valeur}, "prix_sortie": 1}}')


def test_une_devise_inconnue_est_refusee():
    with pytest.raises(ReponseIllisible):
        lire_tarif('{"ligne": "x", "devise": "GBP", "prix_entree": 1, "prix_sortie": 1}')


# ── 3 à 5. Le geste complet ────────────────────────────────────────────────


def test_le_tarif_trouve_est_converti_et_enregistre(session, sources, monkeypatch):
    recus: list = []
    reponse = '{"ligne": "Claude Haiku 4.5", "devise": "USD", "prix_entree": 1, "prix_sortie": 5}'
    monkeypatch.setattr(llm, "demander", _modele(reponse, recus))

    t = asyncio.run(chercher_et_enregistrer(session, "description", "claude-haiku-4-5-20251001"))

    assert (t.prix_entree, t.prix_sortie) == (80, 400)
    assert _valeur(session, "llm_description_prix_entree") == "80"
    assert _valeur(session, "llm_description_prix_sortie") == "400"
    assert "ligne « Claude Haiku 4.5 »" in t.remarque
    assert "taux BCE du 30/09/2026 (1 € = 1,2500 $)" in t.remarque
    #  La grille lue est celle du fournisseur, et c'est tout ce qui part avec le modèle.
    assert sources == ["https://docs.claude.com/en/docs/about-claude/pricing.md"]
    ((usage, message),) = recus
    assert usage == USAGE_TARIF_MODELE
    assert message.startswith(
        "Fournisseur : Claude (Anthropic)\nIdentifiant du modèle : claude-haiku-4-5-20251001\n"
    )
    assert message.endswith(GRILLE)


def test_un_modele_affiche_mais_pas_enregistre_est_refuse(session, sources, monkeypatch):
    recus: list = []
    monkeypatch.setattr(llm, "demander", _modele("{}", recus))
    with pytest.raises(ErreurLLM, match="n'est pas celui qui est enregistré"):
        asyncio.run(chercher_et_enregistrer(session, "description", "gpt-5.6-luna"))
    assert recus == [] and sources == []


def test_seul_le_prix_trouve_s_enregistre(session, sources, monkeypatch):
    reponse = '{"ligne": "x", "devise": "EUR", "prix_entree": 0.5, "prix_sortie": null}'
    monkeypatch.setattr(llm, "demander", _modele(reponse))
    t = asyncio.run(chercher_et_enregistrer(session, "description", "claude-haiku-4-5-20251001"))
    assert (t.prix_entree, t.prix_sortie) == (50, None)
    #  Celui de l'administrateur reste.
    assert _valeur(session, "llm_description_prix_sortie") == "999"


def test_un_modele_absent_de_la_grille_se_dit_et_rien_n_est_ecrit(session, sources, monkeypatch):
    reponse = '{"ligne": null, "devise": "USD", "prix_entree": null, "prix_sortie": null}'
    monkeypatch.setattr(llm, "demander", _modele(reponse))
    with pytest.raises(ErreurLLM, match="ne donne pas le tarif"):
        asyncio.run(chercher_et_enregistrer(session, "description", "claude-haiku-4-5-20251001"))
    assert _valeur(session, "llm_description_prix_entree") is None


def test_une_grille_injoignable_se_dit(session, monkeypatch):
    async def panne(url):
        raise tarif_sources.SourceIndisponible("« x » a répondu 503.")

    monkeypatch.setattr(tarif_sources, "lire_grille", panne)
    with pytest.raises(ErreurLLM, match="Grille de Claude \\(Anthropic\\) indisponible"):
        asyncio.run(chercher_et_enregistrer(session, "description", "claude-haiku-4-5-20251001"))


def test_un_usage_inconnu_est_refuse(session):
    with pytest.raises(ErreurLLM, match="Usage inconnu"):
        asyncio.run(chercher_et_enregistrer(session, "nimporte", "m"))


def test_chaque_fournisseur_nomme_sa_grille():
    from app.utils.llm_fournisseurs import FOURNISSEURS

    for f in FOURNISSEURS.values():
        assert f.page_tarifs.startswith("https://") and f.page_tarifs.endswith(".md"), f.code


def test_la_requete_se_construit_vraiment(monkeypatch):
    """La grille part par un vrai client httpx, transport simulé : un en-tête
    accentué faisait lever httpx AVANT l'envoi — les tests qui remplacent
    `lire_grille` ne le voyaient pas, le premier essai réel si."""
    import httpx

    vrai = httpx.AsyncClient
    transport = httpx.MockTransport(lambda requete: httpx.Response(200, text="| grille |"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: vrai(transport=transport, **kw))
    assert asyncio.run(tarif_sources.lire_grille("https://exemple.test/p.md")) == "| grille |"
