"""Le verdict d'un envoi WhatsApp dit ce qui s'est passé — et distingue trois cas.

## Pourquoi ces tests (19/08/2026)

L'utilisateur a comparé son fil WhatsApp et l'écran **Admin → WhatsApp →
Historique des envois**, et les deux se contredisaient :

    WhatsApp   17/08 09:35  ✓✓ (remis)      18/08 10:56  ✓✓ (remis)
    Historique 17/08 09:35  ⚠ incertain     18/08 10:53  ⚠ incertain
                            « réponse 500 du bridge »

Le message **était parti**. Le bridge, lui, avait répondu 500.

## La cause, et pourquoi elle n'était pas un bug de logique

`POST /send` du bridge fait deux choses de suite :

1. `sock.sendMessage(...)` — **le message part** ;
2. `waitForAck(msgId)` — il attend l'accusé du serveur WhatsApp, 15 s au plus.

Quand l'accusé tardait, l'étape 2 levait, et le `catch` **commun** répondait
`500` — exactement comme si l'étape 1 avait échoué. Deux situations opposées
rendues par une seule réponse : « rien n'est parti » et « c'est parti, je n'ai
pas vu l'accusé ».

Côté API, le verdict `incertain` était donc JUSTE (on ne savait pas), mais sa
raison était fausse et inexploitable. C'est ce que ces tests verrouillent :
**un 202 ne se lit pas comme un 500.**

## Ce qui est vérifié, et dans les deux sens

Un test qui ne vérifierait que « 202 → incertain » ne prouverait pas qu'il sait
distinguer : les trois verdicts sont éprouvés côté à côté, plus le cas où l'on
sait que rien n'est parti (`ConnectError`), qui doit rester REJOUABLE.
"""
import httpx
import pytest

from app.utils import whatsapp as wa


def _reponse(code: int) -> httpx.Response:
    requete = httpx.Request("POST", "http://bridge/send")
    return httpx.Response(code, request=requete, json={"ok": code < 300})


def test_202_est_incertain_et_dit_que_le_message_est_parti(monkeypatch):
    """Le cas de l'incident : émis, accusé non observé."""
    def faux_post(url, json=None, headers=None, timeout=None):
        return _reponse(202)

    class FauxClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, json=None, headers=None):
            return _reponse(202)

    monkeypatch.setattr(wa.httpx, "Client", FauxClient)

    with pytest.raises(wa.EnvoiIncertain) as exc:
        wa._poster_au_bridge("http://bridge/send", {}, {})

    message = str(exc.value)
    assert "émis" in message, (
        "La raison doit dire que le message est PARTI — c'est toute la "
        "différence avec un échec, et c'est ce que l'historique affiche."
    )
    assert "500" not in message, (
        "Le 202 ne doit plus être décrit comme une réponse 500 : c'est "
        "précisément la confusion qui a fait afficher « incertain — réponse "
        "500 du bridge » sur des messages remis."
    )


def test_500_reste_incertain_mais_pour_une_autre_raison(monkeypatch):
    """Un vrai 500 : le bridge a échoué en route, sans dire de quel côté."""
    class FauxClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, json=None, headers=None):
            return _reponse(500)

    monkeypatch.setattr(wa.httpx, "Client", FauxClient)

    with pytest.raises(wa.EnvoiIncertain) as exc:
        wa._poster_au_bridge("http://bridge/send", {}, {})
    assert "500" in str(exc.value)


def test_4xx_est_un_echec_etabli_donc_rejouable(monkeypatch):
    """400/401 : la requête a été refusée sans être traitée. Rien n'est parti."""
    class FauxClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, json=None, headers=None):
            return _reponse(400)

    monkeypatch.setattr(wa.httpx, "Client", FauxClient)

    with pytest.raises(httpx.HTTPStatusError):
        wa._poster_au_bridge("http://bridge/send", {}, {})


def test_connexion_impossible_est_un_echec_etabli(monkeypatch):
    """Aucune connexion : le groupe n'a rien reçu, rejouer est SÛR."""
    class FauxClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, url, json=None, headers=None):
            raise httpx.ConnectError("connexion refusée")

    monkeypatch.setattr(wa.httpx, "Client", FauxClient)

    with pytest.raises(httpx.ConnectError):
        wa._poster_au_bridge("http://bridge/send", {}, {})


def test_les_trois_verdicts_se_distinguent():
    """`verdict_envoi` traduit chaque situation, et jamais « échec » sur un doute."""
    assert wa.verdict_envoi(lambda: None) == (wa.STATUT_ENVOYE, None)

    def incertain():
        raise wa.EnvoiIncertain("émis, accusé non observé")

    statut, erreur = wa.verdict_envoi(incertain)
    assert statut == wa.STATUT_INCERTAIN
    assert "émis" in erreur

    def echec():
        raise httpx.ConnectError("connexion refusée")

    statut, erreur = wa.verdict_envoi(echec)
    assert statut == wa.STATUT_ECHEC


def test_un_envoi_incertain_ne_se_rejoue_jamais():
    """🔴 La règle qui a coûté le triple envoi du 14/08/2026.

    Rejouer un envoi dont on ne sait pas s'il a eu lieu fabrique des doublons
    dans un groupe de copropriétaires — et un doublon ne se retire pas.
    """
    assert wa.STATUT_INCERTAIN in wa.STATUTS_NON_REJOUABLES
    assert wa.STATUT_ENVOYE in wa.STATUTS_NON_REJOUABLES
    assert wa.STATUT_EN_COURS in wa.STATUTS_NON_REJOUABLES
    assert wa.STATUT_ECHEC not in wa.STATUTS_NON_REJOUABLES, (
        "Un échec ÉTABLI doit rester rejouable : c'est la seule situation où "
        "l'on sait que le groupe n'a rien reçu."
    )
