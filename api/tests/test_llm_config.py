"""L'accès au modèle de langage — la clé, et les trois fournisseurs.

## Ce que ce test protège

1. **La clé d'API ne sort jamais de l'API**, même pour un administrateur. C'est
   la règle posée le 03/09/2026 après que `smtp_password` eut voyagé en clair
   dans une réponse HTTP : l'écran ne l'affichait pas, mais elle était lisible
   dans l'onglet réseau du navigateur, dans un cache, dans une capture d'écran.
   *Un secret qu'un écran n'affiche pas mais que l'API transmet est un secret
   exposé : la protection est alors dans le rendu, c'est-à-dire nulle part.*

2. **Les trois fournisseurs ne divergent pas.** Azure OpenAI HÉRITE d'OpenAI —
   il n'en redéfinit que l'URL et l'en-tête d'authentification. Si quelqu'un
   recopiait le corps de requête au lieu d'en hériter, ce test le dirait.
"""
from __future__ import annotations

import pytest

from app.routers.config import MARQUEUR_SECRET, _SECRETS, _valeur_pour_admin
from app.utils.llm import (
    FOURNISSEURS,
    ConfigLLM,
    ErreurLLM,
    Fournisseur,
    FournisseurAzure,
)


# ── 1. Le secret ────────────────────────────────────────────────────────────


def test_la_cle_d_api_ne_sort_JAMAIS_de_l_api():
    """🔴 Le point de sécurité de ce lot."""
    assert "llm_api_key" in _SECRETS
    assert _valeur_pour_admin("llm_api_key", "sk-tres-secret") == MARQUEUR_SECRET


def test_le_marqueur_dit_qu_une_cle_EXISTE_sans_la_donner():
    """L'écran a besoin de savoir si une clé est posée — pas laquelle.

    C'est pourquoi le marqueur n'est pas une chaîne vide : sans lui, l'écran
    redemanderait la clé à chaque visite, et quelqu'un finirait par la
    ressaisir dans un champ qui l'écraserait.
    """
    assert _valeur_pour_admin("llm_api_key", "") == ""
    assert _valeur_pour_admin("llm_api_key", "sk-x") == MARQUEUR_SECRET
    assert MARQUEUR_SECRET != ""


# ── 2. Les trois fournisseurs ───────────────────────────────────────────────


def test_les_trois_standards_sont_proposés():
    assert set(FOURNISSEURS) == {"openai", "anthropic", "azure_openai"}


def test_azure_HÉRITE_du_corps_d_openai():
    """🔴 C'est l'héritage qui porte la ressemblance, pas une copie.

    Azure OpenAI est OpenAI derrière une autre porte : même corps de requête,
    même lecture de la réponse. Si quelqu'un recopiait `corps()` au lieu d'en
    hériter, les deux divergeraient au premier ajustement — et personne ne les
    compare jamais, puisque chacune est cohérente avec elle-même.
    """
    openai = FOURNISSEURS["openai"]
    azure = FOURNISSEURS["azure_openai"]
    assert isinstance(azure, FournisseurAzure)
    assert isinstance(azure, Fournisseur)
    assert type(azure).corps is type(openai).corps
    assert type(azure).lire is type(openai).lire


def test_chaque_fournisseur_a_SA_porte_et_SON_en_tête():
    urls = {c: f.url("mon-modele", "https://x", "2024-06-01") for c, f in FOURNISSEURS.items()}
    assert urls["openai"].endswith("/chat/completions")
    assert urls["anthropic"].endswith("/v1/messages")
    #  Azure met le nom du DÉPLOIEMENT dans l'URL, là où les autres le passent
    #  dans le corps — c'est toute la raison de redéfinir `url()`.
    assert "/openai/deployments/mon-modele/" in urls["azure_openai"]
    assert "api-version=2024-06-01" in urls["azure_openai"]

    entetes = {c: f.entetes("CLE") for c, f in FOURNISSEURS.items()}
    assert entetes["openai"]["Authorization"] == "Bearer CLE"
    assert entetes["anthropic"]["x-api-key"] == "CLE"
    assert entetes["azure_openai"]["api-key"] == "CLE"


def test_la_consigne_voyage_dans_les_trois_formes():
    """Chez Claude la consigne est un champ `system` à part ; ailleurs c'est un
    message de rôle `system`. La divergence est réelle — et c'est la SEULE qui
    justifie de redéfinir `corps()`."""
    for code, f in FOURNISSEURS.items():
        corps = f.corps("m", "CONSIGNE", "MESSAGE", 100)
        assert "CONSIGNE" in str(corps), code
        assert "MESSAGE" in str(corps), code
        assert corps["max_tokens"] == 100, code


# ── 3. On échoue AVANT la requête, avec un message lisible ──────────────────


def _config(**kw) -> ConfigLLM:
    base = dict(
        actif=True,
        fournisseur=FOURNISSEURS["openai"],
        cle="sk-x",
        modele="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        version_api="2024-06-01",
        max_jetons=800,
        delai_s=30,
        envoi_document=True,
    )
    base.update(kw)
    return ConfigLLM(**base)


@pytest.mark.parametrize(
    "champ, valeur, extrait",
    [
        ("actif", False, "désactivé"),
        ("cle", "", "clé"),
        ("modele", "", "modèle"),
    ],
)
def test_une_configuration_incomplète_échoue_AVANT_le_réseau(champ, valeur, extrait):
    """Un 401 met plusieurs secondes et rend un message du fournisseur, pas du
    produit. On le dit nous-mêmes, tout de suite."""
    with pytest.raises(ErreurLLM) as e:
        _config(**{champ: valeur}).verifier()
    assert extrait in str(e.value).lower()


def test_azure_EXIGE_son_point_d_accès():
    """Azure n'a pas d'adresse publique : chaque client a la sienne. Sans elle,
    l'appel partirait vers une chaîne vide."""
    with pytest.raises(ErreurLLM) as e:
        _config(fournisseur=FOURNISSEURS["azure_openai"], base_url="", modele="depl").verifier()
    assert "point d" in str(e.value).lower()
    #  Les deux autres s'en passent : ils ont une adresse par défaut.
    _config().verifier()


def test_le_TEST_de_connexion_n_exige_pas_l_activation():
    """🔴 Constaté à l'écran le 11/09/2026 : « j'ai voulu tester » → « l'assistant
    est désactivé dans l'administration ».

    L'ordre naturel est : je saisis, je teste, PUIS j'active. Exiger l'activation
    avant de pouvoir tester obligeait à ouvrir le service au produit sans savoir
    s'il répond — c'est-à-dire à prendre le risque qu'on cherchait à écarter.

    ⚠️ L'usage NORMAL, lui, continue d'exiger l'activation : c'est elle qui dit
    qu'on accepte d'être facturé.
    """
    cfg = _config(actif=False)
    cfg.verifier(exiger_actif=False)          # le test passe
    with pytest.raises(ErreurLLM):
        cfg.verifier()                        # l'usage, non
