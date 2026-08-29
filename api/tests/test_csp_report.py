"""Le point de collecte des violations de CSP (#536).

Il est **public** — le navigateur poste sans cookie — donc chacune de ses bornes
est une décision de sécurité, et chacune se vérifie ici.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import csp


@pytest.fixture(autouse=True)
def compteurs_neufs():
    """Chaque test part d'un relevé vide : les compteurs sont un état de module."""
    csp._violations.clear()
    csp._recus = 0
    csp._ignores = 0
    #  ⚠️ La limite de débit est un état PARTAGÉ entre tests : sans cette remise
    #  à zéro, le troisième test se fait couper par le deuxième et mesure la
    #  mauvaise borne. Elle a d'ailleurs coupé au premier jet — c'est la preuve
    #  qu'elle fonctionne, et la raison de la remettre à zéro ici.
    csp.limiter.reset()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


ANCIEN_FORMAT = {
    "csp-report": {
        "document-uri": "https://5hostachy.fr/",
        "violated-directive": "script-src 'self'",
        "effective-directive": "script-src",
        "blocked-uri": "inline",
    }
}

NOUVEAU_FORMAT = {
    "body": {
        "documentURL": "https://5hostachy.fr/",
        "effectiveDirective": "style-src-attr",
        "blockedURL": "inline",
    }
}


def test_les_DEUX_formats_de_rapport_sont_lus(client):
    """⚠️ Le point qui ferait un relevé vide sur la moitié du parc.

    `report-uri` (ancien) et la Reporting API (nouveau) coexistent selon les
    navigateurs. N'en lire qu'un donnerait « aucune violation » — et un relevé
    vide, ici, se lit comme une bonne nouvelle.
    """
    assert client.post("/csp-report", json=ANCIEN_FORMAT).status_code == 204
    assert client.post("/csp-report", json=NOUVEAU_FORMAT).status_code == 204
    directives = {d for d, _ in csp._violations}
    assert directives == {"script-src", "style-src-attr"}


def test_une_violation_repetee_est_COMPTEE_pas_dupliquee(client):
    """Une page viole à chaque chargement : c'est un compte, pas une liste."""
    for _ in range(5):
        client.post("/csp-report", json=ANCIEN_FORMAT)
    assert len(csp._violations) == 1
    assert csp._violations[("script-src", "inline")] == 5


def test_un_corps_illisible_rend_204_et_se_compte_a_part(client):
    """Un 4xx ferait réessayer le navigateur en boucle.

    Et le compter à part, plutôt que de l'ignorer, évite de lire « aucune
    violation » alors qu'on ne sait pas lire ce qui arrive.
    """
    assert client.post("/csp-report", content=b"pas du json").status_code == 204
    assert client.post("/csp-report", json={"inconnu": 1}).status_code == 204
    assert csp._ignores == 2
    assert len(csp._violations) == 0


def test_la_limite_de_debit_protege_un_point_PUBLIC(client):
    """La borne qui compte le plus : cet endpoint est ouvert, sans cookie.

    Trouvée en écrivant le test du plafond, qui envoyait 210 rapports et n'en a
    vu passer que 60 — la limite faisait son travail avant lui.
    """
    codes = [client.post("/csp-report", json=ANCIEN_FORMAT).status_code for _ in range(70)]
    assert 429 in codes, "un point public sans limite de débit est une invitation"
    assert codes.count(204) == 60


def test_le_plafond_de_cles_borne_la_memoire(client):
    """Un envoi forgé ne doit pas faire croître la mémoire sans fin.

    ⚠️ Et le dépassement doit rester VISIBLE : `ignores` monte, `plafond_atteint`
    passe à vrai. Un plafond silencieux ferait conclure « plus rien à corriger ».
    """
    #  Éprouvé sur la FONCTION `retenir` et non par HTTP : la limite de débit
    #  (60/min, vérifiée juste au-dessus) couperait avant qu'on atteigne le
    #  plafond. Deux bornes distinctes, deux tests distincts — et surtout, la
    #  décision n'est pas RECOPIÉE ici, sans quoi le test se vérifierait
    #  lui-même.
    refus = sum(not csp.retenir(("img-src", f"https://x/{i}")) for i in range(csp.PLAFOND_CLES + 10))
    assert len(csp._violations) == csp.PLAFOND_CLES
    assert refus == 10
    #  Une clé DÉJÀ connue passe encore : le plafond borne la variété, pas le compte.
    assert csp.retenir(("img-src", "https://x/0")) is True


def test_une_url_tres_longue_est_TRONQUEE_avant_de_servir_de_cle(client):
    """L'URL vient du navigateur : elle est bornée avant tout usage."""
    _, bloque = csp._extraire(
        {"csp-report": {"effective-directive": "img-src", "blocked-uri": "https://x/" + "a" * 5000}}
    )
    assert len(bloque) == csp.LONGUEUR_MAX


def test_le_releve_est_reserve_aux_admins(client):
    """Il expose des URL de pages visitées : ce n'est pas public."""
    assert client.get("/admin/csp-violations").status_code in (401, 403)
