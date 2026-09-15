"""La génération de synthèse est BORNÉE — c'est le seul appel payant du dépôt.

## Pourquoi ce fichier

Partout ailleurs ici, un appel en trop coûte du CPU. `POST
/prestataires/contrats/{id}/synthese` fait lire un contrat entier par un modèle
de langage : chaque appel se lit sur une facture. Un double-clic, une tempête de
réessais, un onglet resté ouvert sur un écran qui se recharge — chaque tour est
facturé.

Les points d'entrée sensibles du dépôt sont bornés depuis toujours (`/auth/*`,
`/csp`, `/telemetry`). Celui-ci ne l'était pas : sa nature nouvelle — dépenser —
n'avait pas d'équivalent au moment où ces limites ont été posées, et rien ne
rappelait de l'y ajouter.

## 🔴 Ce que ce fichier NE dit PAS

**Que le budget est protégé.** Une limite par minute ne connaît ni le prix d'un
appel, ni le solde restant : c'est un garde-BOUCLE. Le seul plafond de dépense
qui vaille se pose sur le compte du fournisseur. L'écrire autrement serait une
consigne fausse, et ce dépôt les tient pour pires qu'absentes.

**Que chaque utilisateur a son quota.** Le seau est global : `get_remote_address`
lit `request.client.host`, or `start.sh` lance uvicorn sans `--proxy-headers`,
donc derrière Caddy toutes les requêtes portent l'adresse du proxy. C'est vrai de
TOUTES les limites du dépôt, `/auth/login` compris.
"""
from __future__ import annotations

import pytest


#: Le nom sous lequel slowapi enregistre l'endpoint. Il suit le module : le jour
#: où la route déménage, ce contrôle échoue et dit où regarder — c'est voulu.
ROUTE_GENERATION = "app.routers.contrats_synthese.proposer_synthese"


def _limites() -> dict:
    """Ce que slowapi consulte RÉELLEMENT à chaque requête.

    ⚠️ `_route_limits` est un attribut privé, et c'est un choix assumé : c'est la
    structure que slowapi interroge, donc la seule qui prouve qu'une limite
    s'applique. Relever le décorateur dans le texte source prouverait seulement
    qu'il est écrit — pas qu'il s'attache, ni qu'il vise la bonne fonction.
    """
    from app.routers import auth, contrats_synthese  # noqa: F401  (enregistre les limites)
    from app.utils.limiter import limiter

    limites = getattr(limiter, "_route_limits", None)
    if limites is None:
        pytest.skip("slowapi a changé de forme interne — contrôle NON MESURÉ, pas réussi.")
    assert limites, "Cas zéro : aucune limite enregistrée — lecture inopérante."
    #  Le témoin : un endpoint borné depuis toujours. S'il manque, c'est la
    #  lecture qui est cassée, pas la synthèse qui est nue.
    assert any("auth" in cle for cle in limites), (
        "Cas zéro : aucune limite d'authentification relevée — lecture inopérante."
    )
    return limites


def test_la_generation_de_synthese_est_bornee():
    """🔴 Le contrôle central. Retirer le décorateur le fait échouer."""
    limites = _limites()
    assert ROUTE_GENERATION in limites, (
        "La génération de synthèse n'est bornée par RIEN. C'est le seul point "
        "d'entrée payant du dépôt : une boucle y facture chaque tour.\n"
        f"  Relevé : {sorted(limites)}"
    )


def test_la_limite_est_exprimee_PAR_MINUTE():
    """Une limite horaire ou journalière ne protège pas d'une boucle.

    Une boucle fait ses cent tours en quelques secondes : c'est la fenêtre courte
    qui l'arrête. Un plafond par jour laisserait passer la rafale, puis bloquerait
    le conseil syndical pour le reste de la journée — le pire des deux.
    """
    from app.routers.contrats_synthese import LIMITE_GENERATION

    assert "minute" in LIMITE_GENERATION, (
        f"La limite vaut « {LIMITE_GENERATION} » : elle ne borne pas une rafale."
    )


def test_la_route_est_montee_et_refuse_un_anonyme_sans_planter():
    """Le FAIT, pas la déclaration : l'application répond vraiment sur ce chemin.

    🔴 Ce contrôle existe pour une raison précise : `@limiter.limit` EXIGE un
    paramètre `request` dans la signature. L'oublier ne casse rien au montage —
    l'endpoint paraît sain jusqu'au premier clic, où il lève. Un contrôle qui ne
    lirait que la table des routes passerait au vert sur ce défaut-là.

    ⚠️ Un anonyme est refusé par la DÉPENDANCE, avant que la limite ne compte :
    ce n'est donc pas elle qui protège d'un flot anonyme, c'est
    l'authentification. Dire l'inverse serait une consigne fausse.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    reponse = client.post("/prestataires/contrats/1/synthese", json={})

    assert reponse.status_code in (401, 403), (
        f"Attendu un refus d'authentification, reçu {reponse.status_code}. "
        "Un 500 signalerait une signature refusée par slowapi ; un 404, une "
        "route non montée."
    )
