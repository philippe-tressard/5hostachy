"""Le tarif d'un modèle, demandé à l'assistant (30/09/2026).

Ce que ce test protège :

1. **Un prix relu est un prix en centimes entiers** — l'unité que stockent les
   champs `prix_entree` / `prix_sortie` d'un usage : un montant ne se garde
   jamais en flottant, et 0,20 € par million doit devenir 20, pas 19.
2. **Un prix absurde est refusé**, pas enregistré : un booléen, une chaîne, un
   négatif, un prix par millier pris pour un prix par million.
3. **« Je ne sais pas » se dit** : deux `null` rendent une erreur lisible,
   jamais deux champs vidés en silence.
4. **Seuls le fournisseur et le modèle partent** : le message ne porte rien
   d'autre.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import ConfigSite
from app.utils import llm
from app.utils.description_format import ReponseIllisible
from app.utils.llm import ErreurLLM
from app.utils.tarif_modele import USAGE_TARIF_MODELE, lire_tarif, proposer_tarif


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
            f"llm_{USAGE_TARIF_MODELE}_modele": "modele-qui-repond",
        }.items():
            s.add(ConfigSite(cle=cle, valeur=valeur))
        s.commit()
        yield s


def _modele(texte: str, recus: list | None = None):
    async def faux(session, *, usage, message, **_):
        if recus is not None:
            recus.append((usage, message))
        return SimpleNamespace(texte=texte)

    return faux


# ── 1. La lecture ──────────────────────────────────────────────────────────


def test_un_prix_decimal_devient_des_centimes_entiers():
    t = lire_tarif('{"prix_entree": 0.2, "prix_sortie": 1.2, "remarque": "0,22 $ au taux 0,92."}')
    assert (t.prix_entree, t.prix_sortie) == (20, 120)
    assert t.remarque == "0,22 $ au taux 0,92."


def test_un_bloc_de_code_autour_du_json_est_tolere():
    t = lire_tarif('```json\n{"prix_entree": 3, "prix_sortie": 15, "remarque": ""}\n```')
    assert (t.prix_entree, t.prix_sortie) == (300, 1500)


def test_un_seul_prix_connu_laisse_l_autre_vide():
    t = lire_tarif('{"prix_entree": 1, "prix_sortie": null, "remarque": "x"}')
    assert (t.prix_entree, t.prix_sortie) == (100, None)


# ── 2. Ce qui n'est pas un prix ────────────────────────────────────────────


@pytest.mark.parametrize(
    "valeur",
    ["true", '"0,20"', "-1", "1500", "[1]"],
)
def test_un_prix_qui_n_en_est_pas_un_est_refuse(valeur):
    with pytest.raises(ReponseIllisible):
        lire_tarif(f'{{"prix_entree": {valeur}, "prix_sortie": 1, "remarque": ""}}')


def test_une_reponse_en_prose_est_refusee():
    with pytest.raises(ReponseIllisible):
        lire_tarif("Le prix est de 0,20 € par million.")


# ── 3 et 4. L'appel ────────────────────────────────────────────────────────


def test_seuls_le_fournisseur_et_le_modele_partent(session, monkeypatch):
    recus: list = []
    monkeypatch.setattr(
        llm,
        "demander",
        _modele('{"prix_entree": 0.8, "prix_sortie": 4, "remarque": "r"}', recus),
    )
    t = asyncio.run(proposer_tarif(session, "  claude-haiku-4-5  "))
    assert (t.prix_entree, t.prix_sortie) == (80, 400)
    ((usage, message),) = recus
    assert usage == USAGE_TARIF_MODELE
    assert message == "Fournisseur : Claude (Anthropic)\nIdentifiant du modèle : claude-haiku-4-5"


def test_deux_prix_inconnus_se_disent(session, monkeypatch):
    monkeypatch.setattr(
        llm, "demander", _modele('{"prix_entree": null, "prix_sortie": null, "remarque": ""}')
    )
    with pytest.raises(ErreurLLM, match="ne connaît pas le tarif"):
        asyncio.run(proposer_tarif(session, "modele-inconnu"))


def test_une_reponse_illisible_devient_une_erreur_de_l_assistant(session, monkeypatch):
    monkeypatch.setattr(llm, "demander", _modele("désolé"))
    with pytest.raises(ErreurLLM, match="format attendu"):
        asyncio.run(proposer_tarif(session, "m"))


def test_sans_modele_rien_ne_part(session, monkeypatch):
    recus: list = []
    monkeypatch.setattr(llm, "demander", _modele("{}", recus))
    with pytest.raises(ErreurLLM, match="Choisissez d'abord un modèle"):
        asyncio.run(proposer_tarif(session, "   "))
    assert recus == []
