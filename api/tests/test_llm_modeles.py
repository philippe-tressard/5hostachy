"""Le catalogue des modèles que la clé enregistrée peut appeler — `llm_modeles` (#1569).

Sorti de `llm.py` le 27/09/2026 : `test_llm_config.py` en éprouve les branches
courantes par l'import ré-exporté (`app.utils.llm`), jamais par le nom du module. Ici,
le module, avec ce qu'il PROMET à l'écran : une réponse toujours LISIBLE, jamais une
exception réseau — « le fait, pas le catalogue » :

1. la requête part vers la bonne adresse, avec l'en-tête d'authentification du
   fournisseur, et la clé ne revient JAMAIS dans la réponse ;
2. chaque situation sans liste (Azure, service injoignable, 401/403, 4xx/5xx, corps
   illisible, liste vide) rend `listable: False` et un motif — jamais un menu vide ;
3. une vraie liste rend les modèles de conversation, et eux seuls ;
4. sans clé enregistrée, l'échec est franc (`ErreurLLM`) AVANT toute requête réseau ;
5. l'ancien chemin d'import reste le même objet : les appelants n'ont pas bougé.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
import pytest

from app.models.core import ConfigSite
from app.utils import llm, llm_modeles
from app.utils.llm import ErreurLLM
from app.utils.llm_modeles import modeles_disponibles


def _config(session, **valeurs):
    base = {"llm_actif": "1", "llm_fournisseur": "openai", "llm_api_key": "sk-secret-123"}
    base.update(valeurs)
    for cle, valeur in base.items():
        session.add(ConfigSite(cle=cle, valeur=valeur))
    session.commit()
    return session


class _Reponse:
    def __init__(self, code=200, charge=None, illisible=False):
        self.status_code = code
        self._charge = charge
        self._illisible = illisible

    def json(self):
        if self._illisible:
            raise ValueError("pas du JSON")
        return self._charge


@pytest.fixture()
def appels(monkeypatch):
    """Le client HTTP factice : enregistre `(url, en-têtes, délai)` et rend `reponse`."""
    vus: list[dict] = []
    etat = {"reponse": _Reponse(200, {"data": []})}

    class _Client:
        def __init__(self, *a, **k):
            vus.append({"timeout": k.get("timeout")})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, **k):
            vus[-1].update(url=url, headers=k.get("headers"))
            if isinstance(etat["reponse"], Exception):
                raise etat["reponse"]
            return etat["reponse"]

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    return vus, etat


def _lister(session):
    return asyncio.run(modeles_disponibles(session))


# ── La requête ──────────────────────────────────────────────────────────────


def test_la_requete_va_au_catalogue_du_fournisseur_avec_sa_cle(session, appels):
    vus, _ = appels
    _config(session)

    _lister(session)

    [appel] = vus
    assert appel["url"].endswith("/models")
    assert appel["headers"]["Authorization"] == "Bearer sk-secret-123"


def test_le_delai_est_celui_de_la_configuration(session, appels):
    vus, _ = appels
    _config(session)

    _lister(session)

    assert vus[0]["timeout"] is not None and vus[0]["timeout"] > 0


def test_la_cle_ne_revient_jamais_dans_la_reponse(session, appels):
    _, etat = appels
    etat["reponse"] = _Reponse(200, {"data": [{"id": "gpt-4o", "created": 1}]})
    _config(session)

    assert "sk-secret-123" not in repr(_lister(session))


# ── Sans liste : toujours une réponse lisible ───────────────────────────────


def test_azure_n_expose_pas_de_liste_et_ne_fait_aucune_requete(session, appels):
    vus, _ = appels
    _config(session, llm_fournisseur="azure_openai", llm_base_url="https://client.exemple.test")

    r = _lister(session)

    assert r["listable"] is False and r["modeles"] == []
    assert "n'expose pas la liste de ses déploiements" in r["motif"]
    assert vus == [], "aucun appel réseau : il n'y a pas d'adresse à interroger"


def test_un_service_injoignable_rend_un_motif_pas_une_exception(session, appels):
    _, etat = appels
    etat["reponse"] = httpx.ConnectError("refusée")
    _config(session)

    assert _lister(session) == {
        "listable": False,
        "motif": "Le service n'a pas pu être joint.",
        "modeles": [],
    }


def test_un_delai_depasse_est_aussi_un_motif(session, appels):
    _, etat = appels
    etat["reponse"] = httpx.ReadTimeout("trop long")
    _config(session)

    assert _lister(session)["motif"] == "Le service n'a pas pu être joint."


@pytest.mark.parametrize("code", [401, 403])
def test_une_cle_sans_droit_de_lister_n_est_pas_une_cle_invalide(session, appels, code):
    """Une clé restreinte à `/chat/completions` synthétise très bien : on ne la dit pas fausse."""
    _, etat = appels
    etat["reponse"] = _Reponse(code)
    _config(session)

    r = _lister(session)

    assert r["listable"] is False
    assert "permission « models »" in r["motif"]


@pytest.mark.parametrize("code", [400, 404, 429, 500, 503])
def test_une_autre_erreur_du_fournisseur_nomme_son_code_et_se_journalise(
    session, appels, caplog, code
):
    _, etat = appels
    etat["reponse"] = _Reponse(code)
    _config(session)

    with caplog.at_level(logging.WARNING, logger="hostachy.llm"):
        r = _lister(session)

    assert r == {"listable": False, "motif": f"Le fournisseur a répondu {code}.", "modeles": []}
    assert f"Liste des modèles openai → {code}" in caplog.text


#  🔴 DÉFAUT RÉVÉLÉ (#1569, 02/10/2026) : `llm_modeles` rattrape `ValueError`, `KeyError` et
#  `TypeError` autour de `lire_modeles`, mais pas `AttributeError`. Un service (ou un proxy
#  « compatible OpenAI ») qui répond un JSON valide d'une AUTRE forme — un tableau, ou
#  `{"data": "…"}` — fait lever `reponse.get(...)` / `m.get(...)` : l'exception sort, l'écran
#  d'administration reçoit un 500 au lieu du motif « Liste illisible — format inattendu. »
#  que la fonction promet (« rend toujours une réponse LISIBLE, jamais une exception »).
#  Non corrigé ici (lot de tests seuls) : les deux cas restent en xfail strict, et passeront
#  au vert — donc feront échouer le xfail — le jour où le défaut sera corrigé.
_FORME_INATTENDUE = pytest.mark.xfail(
    strict=True,
    raises=AttributeError,
    reason="AttributeError non rattrapée par llm_modeles.modeles_disponibles (#1569)",
)


@pytest.mark.parametrize(
    "reponse",
    [
        pytest.param(_Reponse(200, illisible=True), id="json-invalide"),
        pytest.param(
            _Reponse(200, charge=["pas", "un", "objet"]), id="tableau", marks=_FORME_INATTENDUE
        ),
        pytest.param(
            _Reponse(200, charge={"data": "pas une liste"}),
            id="data-chaine",
            marks=_FORME_INATTENDUE,
        ),
        pytest.param(_Reponse(200, charge={"data": [{"sans_id": 1}]}), id="sans-id"),
    ],
)
def test_un_corps_illisible_ne_leve_pas(session, appels, reponse):
    _, etat = appels
    etat["reponse"] = reponse
    _config(session)

    r = _lister(session)

    assert r["listable"] is False and r["modeles"] == []
    assert r["motif"]  # toujours une raison à afficher


def test_une_liste_vide_n_est_pas_une_liste(session, appels):
    """Le cas zéro : rendre `listable` avec zéro modèle ferait choisir dans un menu sans entrée."""
    _, etat = appels
    etat["reponse"] = _Reponse(200, {"data": []})
    _config(session)

    assert _lister(session) == {
        "listable": False,
        "motif": "Aucun modèle de conversation proposé.",
        "modeles": [],
    }


def test_une_liste_sans_modele_de_conversation_n_est_pas_une_liste_non_plus(session, appels):
    _, etat = appels
    etat["reponse"] = _Reponse(
        200,
        {
            "data": [
                {"id": "whisper-1", "created": 1},
                {"id": "text-embedding-3-small", "created": 2},
            ]
        },
    )
    _config(session)

    assert _lister(session)["listable"] is False


# ── Une vraie liste ─────────────────────────────────────────────────────────


def test_une_vraie_liste_ne_garde_que_les_modeles_de_conversation_du_plus_recent(session, appels):
    _, etat = appels
    etat["reponse"] = _Reponse(
        200,
        {
            "data": [
                {"id": "gpt-4o-mini", "created": 100},
                {"id": "whisper-1", "created": 500},
                {"id": "gpt-4o", "created": 300},
                {"id": "text-embedding-3-small", "created": 400},
            ]
        },
    )
    _config(session)

    r = _lister(session)

    assert r["listable"] is True and r["motif"] == ""
    assert [m["id"] for m in r["modeles"]] == ["gpt-4o", "gpt-4o-mini"]
    assert all(set(m) == {"id", "libelle"} for m in r["modeles"])


# ── Sans clé : franc, avant tout réseau ─────────────────────────────────────


def test_sans_cle_l_echec_est_franc_et_aucune_requete_part(session, appels):
    vus, _ = appels
    _config(session, llm_api_key="")

    with pytest.raises(ErreurLLM, match="Aucune clé d'API"):
        _lister(session)

    assert vus == []


def test_l_assistant_desactive_n_empeche_pas_de_lister(session, appels):
    """On liste pour DÉCIDER d'activer : l'activation n'est pas exigée (comme au test de connexion)."""
    _, etat = appels
    etat["reponse"] = _Reponse(200, {"data": [{"id": "gpt-4o", "created": 1}]})
    _config(session, llm_actif="0")

    assert _lister(session)["listable"] is True


def test_l_absence_de_modele_choisi_n_empeche_pas_de_lister(session, appels):
    _, etat = appels
    etat["reponse"] = _Reponse(200, {"data": [{"id": "gpt-4o", "created": 1}]})
    _config(session, llm_modele="")

    assert _lister(session)["listable"] is True


# ── Compatibilité ───────────────────────────────────────────────────────────


def test_les_appelants_importent_toujours_depuis_app_utils_llm():
    assert llm.modeles_disponibles is llm_modeles.modeles_disponibles
