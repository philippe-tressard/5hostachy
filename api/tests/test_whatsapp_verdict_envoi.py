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
raison était fausse et inexploitable. Ce que verrouille désormais la table de
`test_whatsapp_scheduler.py` : **un 202 ne se lit pas comme un 500.**

## Ce qui est vérifié ici, et ce qui l'est ailleurs

Un test qui ne vérifierait que « 202 → incertain » ne prouverait pas qu'il sait
distinguer : les trois verdicts de `verdict_envoi` sont éprouvés côte à côte, et
la règle de rejeu qui en découle — un échec ÉTABLI reste rejouable, un doute
jamais.

La traduction d'une réponse du bridge en verdict (202, 4xx, 5xx, connexion
impossible) vit dans les tables de `test_whatsapp_scheduler.py`
(`test_classification_des_reponses_du_bridge`, `…_des_pannes_de_transport`) : une
seule table par question, plutôt qu'un faux client recopié par cas.
"""

import httpx

from app.utils import whatsapp as wa


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
