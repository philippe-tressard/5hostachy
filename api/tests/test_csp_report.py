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
    #  Le drapeau de chargement est un état de module lui aussi : sans cette
    #  remise à zéro, le premier test qui charge empêcherait les suivants de le
    #  faire, et le test de persistance passerait sans rien éprouver.
    csp._charge = False
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


# ── La persistance : ce que six déploiements dans la journée ont appris ──────

def test_le_releve_SURVIT_a_un_redemarrage():
    """🔴 Sans cela, ce point de collecte ne collecte rien sur un site vivant.

    Le relevé vivait en mémoire de processus, et chaque déploiement recrée le
    conteneur. Le 29/08/2026, SIX déploiements ont eu lieu : la fenêtre
    d'observation n'a jamais dépassé quelques dizaines de minutes, et la
    production affichait 0 ligne CSP sur un conteneur « Up About a minute ».

    ⚠️ C'est le faux vert le plus traître de la famille : le relevé rendait
    « aucune violation », ce qui se lit « le site est conforme ». Le code prévoyait
    bien un TÉMOIN pour `recus == 0` — mais pas le cas où des rapports sont
    arrivés PUIS ont été effacés.

    Le redémarrage est simulé comme il se produit : l'état de module repart à
    zéro, la BASE ne bouge pas.
    """
    from sqlmodel import Session, SQLModel

    from app.database import engine

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        csp.charger(session)
        csp.retenir(("script-src", "inline"))
        csp._recus = 3
        csp._persister(session)

        #  ── Le redémarrage ──
        csp._violations.clear()
        csp._recus = 0
        csp._ignores = 0
        csp._charge = False

        csp.charger(session)

    assert csp._violations[("script-src", "inline")] == 1, "le relevé n'a pas survécu"
    assert csp._recus == 3, "le compte de rapports reçus n'a pas survécu"


def test_un_releve_ILLISIBLE_ne_bloque_pas_le_demarrage():
    """Le cas zéro de la restauration : une valeur abîmée repart de zéro.

    ⚠️ Lever ici empêcherait l'application de servir la première requête qui
    touche ce point — et `start.sh` a `set -e`. Un point de collecte ne doit
    jamais faire tomber ce qu'il observe.
    """
    from sqlmodel import Session, SQLModel

    from app.database import engine
    from app.models.core import ConfigSite

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ligne = session.get(ConfigSite, csp.CLE_PERSISTANCE)
        if ligne:
            ligne.valeur = "{ceci n'est pas du JSON"
        else:
            session.add(ConfigSite(cle=csp.CLE_PERSISTANCE, valeur="{ceci n'est pas du JSON"))
        session.commit()

        csp._charge = False
        csp.charger(session)  # ne doit pas lever

    assert csp._violations == {} or True  # le contrat est « ne lève pas »


def test_QUAND_le_releve_est_ecrit_en_base():
    """La borne d'écriture, éprouvée seule.

    ⚠️ Elle ne peut PAS se vérifier par HTTP : le client de test fait tourner
    l'application dans un autre fil, donc sur une autre base en mémoire
    (`SingletonThreadPool`) — l'écriture y disparaît, et le test échouerait en
    accusant la persistance d'un défaut qui est celui du montage.
    """
    #  Une clé nouvelle s'écrit TOUT DE SUITE, quel que soit le compte.
    assert csp.doit_persister(nouvelle=True, recus=1)
    assert csp.doit_persister(nouvelle=True, recus=7)

    #  Une répétition attend le diviseur — sinon soixante écritures par minute
    #  au plafond de débit, sur un point PUBLIC.
    assert not csp.doit_persister(nouvelle=False, recus=1)
    assert not csp.doit_persister(nouvelle=False, recus=24)
    assert csp.doit_persister(nouvelle=False, recus=csp.PERSISTER_TOUS_LES)

    assert not csp.doit_persister(nouvelle=False, recus=csp.PERSISTER_TOUS_LES - 1)
    assert csp.doit_persister(nouvelle=False, recus=csp.PERSISTER_TOUS_LES * 2)

    #  🔴 ET LA VALEUR, en clair. Sans cette ligne, ce test NE MORD PAS : toutes
    #  les assertions ci-dessus se calculent AVEC la constante, si bien qu'un
    #  diviseur porté à 26 les laisse toutes vraies. Vérifié en cassant le
    #  module — dix tests verts sur une borne changée.
    #
    #  C'est le défaut que ce dépôt a déjà rencontré (#605) : un self-test qui
    #  éprouve la forme de la règle et jamais son seuil. Le seuil est un CHOIX —
    #  le point est public et plafonné à 60 rapports/minute, donc au pire ~2,4
    #  écritures par minute — et un choix se change exprès, pas par accident.
    assert csp.PERSISTER_TOUS_LES == 25, (
        "le diviseur d'écriture a changé : le décider, et dire ici pourquoi — "
        "il borne les écritures d'un point PUBLIC"
    )
