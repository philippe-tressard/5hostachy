"""Une relève qui ÉCHOUE ne doit pas dire « aucun message non lu » (08/09/2026).

## Le défaut, trouvé par le point 6 du pré-check

    ERROR app.utils.courriel_boite — Relève de la boîte des réponses :
          b'[UNAVAILABLE] Account is temporarily unavailable.'
    INFO  app.utils.courriel_boite — Réponses par courriel : relève effectuée,
          aucun message non lu

Deux lignes consécutives, la seconde démentant la première. Le commentaire qui
accompagnait cette ligne affirmait qu'elle *« prouve que la relève est vivante
et que la boîte est simplement vide »* — et elle s'imprimait précisément sur le
passage où la relève était morte.

🔴 Une boîte injoignable et une boîte vide rendaient donc **le même journal**.
Une réponse de résident arrivée pendant une indisponibilité se lisait comme une
absence de réponse : c'est `standards/04` §2 — *une sortie vide n'est pas un
constat* — appliqué à un tuyau au lieu d'un contrôle.

⚠️ Ce test regarde ce que la fonction ÉCRIT, pas ce qu'elle rend : le compte
`{0, 0, 0, 0}` est identique dans les deux cas, et c'est justement le problème.
Le journal est la seule sortie qui les distingue, donc c'est lui qu'on mesure.
"""
from __future__ import annotations

import logging

import pytest

from app.utils import courriel_boite

_RASSURANT = "aucun message non lu"


@pytest.fixture()
def imap_actif(monkeypatch):
    """La relève se croit configurée — c'est la connexion qui échouera."""
    monkeypatch.setattr(
        courriel_boite, "config_imap",
        lambda _session: {
            "imap_enabled": "true", "imap_host": "imap.invalide", "imap_port": "993",
            "imap_user": "essai@invalide", "imap_password": "x", "imap_dossier": "INBOX",
        },
    )


def test_une_releve_INJOIGNABLE_ne_dit_pas_que_la_boite_est_vide(caplog, imap_actif, monkeypatch):
    """🔴 Le cas observé en production le 08/09/2026."""
    def _tombe(*_a, **_kw):
        raise OSError("[UNAVAILABLE] Account is temporarily unavailable.")

    monkeypatch.setattr(courriel_boite.imaplib, "IMAP4_SSL", _tombe)

    with caplog.at_level(logging.INFO, logger="app.utils.courriel_boite"):
        courriel_boite.relever()

    messages = [enr.getMessage() for enr in caplog.records]
    assert any("Relève de la boîte" in m for m in messages), (
        "l'échec doit être journalisé en ERROR — sans quoi le point 6 du "
        "pré-check et l'alerte quotidienne ne le voient pas"
    )
    assert not any(_RASSURANT in m for m in messages), (
        "la relève a échoué et le journal annonce quand même une boîte vide : "
        "une réponse arrivée pendant la panne se lira comme une absence de réponse."
    )


def test_une_releve_REUSSIE_et_vide_le_dit_TOUJOURS(caplog, imap_actif, monkeypatch):
    """Le pendant, sans lequel le correctif serait de supprimer la ligne.

    Cette trace existe depuis le 04/09/2026 pour une raison : sans elle,
    « désactivée » et « activée, boîte vide » sont indiscernables, et la
    question « est-ce que ça tourne ? » reste sans réponse. La distinguer d'un
    échec ne doit pas la faire disparaître.
    """
    class _BoiteVide:
        def login(self, *_a):
            return ("OK", [b""])

        def select(self, *_a, **_k):
            return ("OK", [b"0"])

        def search(self, *_a):
            return ("OK", [b""])

        def logout(self):
            return ("BYE", [b""])

    monkeypatch.setattr(courriel_boite.imaplib, "IMAP4_SSL", lambda *_a, **_k: _BoiteVide())

    with caplog.at_level(logging.INFO, logger="app.utils.courriel_boite"):
        courriel_boite.relever()

    messages = [enr.getMessage() for enr in caplog.records]
    assert any(_RASSURANT in m for m in messages), (
        "une relève réussie sur une boîte vide doit le DIRE : sans cette trace, "
        "une relève morte et une relève sans courrier se ressemblent."
    )
