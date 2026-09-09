"""Passager ou persistant : un échec ne crie qu'après s'être répété (#858).

## L'incident

Le 09/09/2026 à 10:20, une relève IMAP a échoué sur un
`[UNAVAILABLE] Account is temporarily unavailable` du fournisseur de messagerie.
Le cycle suivant, dix minutes plus tard, a réussi. Rien n'était perdu — la boîte
n'est pas touchée quand la connexion échoue, et les messages sont relus.

Mais l'échec était journalisé en `ERROR` dès la première occurrence : il a fait
échouer le point 6 du pré-check pendant une heure et aurait déclenché l'alerte
quotidienne, sur un système sain, pour une secousse déjà résolue.

🔴 La bonne règle était écrite dans le fichier même qui l'enfreignait — *« une
erreur qui se répète est un appel, pas du bruit »* — et rien ne l'appliquait.

## Ce que ces tests verrouillent

La décision est une fonction **pure** : elle s'éprouve sans horloge, sans réseau
et sans journal. Le compteur, lui, doit se remettre à zéro — c'est le seul défaut
possible de ce module, et il est silencieux.
"""
from __future__ import annotations

import logging

from app.utils.echecs_repetes import SEUIL, CompteurEchecs, niveau


def test_le_premier_echec_ne_CRIE_pas():
    """Une secousse ne doit réveiller personne."""
    assert niveau(1, seuil=3) == logging.WARNING


def test_le_seuil_atteint_CRIE():
    """Trois échecs d'affilée, c'est une panne — elle doit se signaler."""
    assert niveau(3, seuil=3) == logging.ERROR
    assert niveau(10, seuil=3) == logging.ERROR


def test_juste_avant_le_seuil_ne_crie_pas_encore():
    assert niveau(2, seuil=3) == logging.WARNING


def test_aucun_echec_n_est_pas_un_avertissement():
    """🔴 Cas zéro : sans lui, un compteur à zéro passerait pour un échec."""
    assert niveau(0, seuil=3) == logging.INFO


def test_le_SEUIL_par_defaut_laisse_passer_une_secousse():
    """Le seuil se règle sur le RÉGIME de la panne cherchée, pas sur la tâche.

    Trois cycles de dix minutes = une demi-heure d'affilée. Si quelqu'un le
    ramenait à 1, ce module ne servirait plus à rien — et rien ne le dirait.
    """
    assert SEUIL >= 2, "un seuil de 1 rend le module inutile : tout crie de nouveau."
    assert niveau(1) == logging.WARNING


def test_le_compteur_monte_puis_se_REMET_A_ZERO(caplog):
    """Le défaut silencieux : un succès non compté fait crier trois secousses
    espacées de trois semaines."""
    compteur = CompteurEchecs("essai", seuil=3)
    journal = logging.getLogger("essai_echecs")

    with caplog.at_level(logging.WARNING, logger="essai_echecs"):
        assert compteur.echec(journal, "panne %s", "A") == 1
        assert compteur.echec(journal, "panne %s", "B") == 2
    assert [r.levelno for r in caplog.records] == [logging.WARNING] * 2

    compteur.succes()
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="essai_echecs"):
        assert compteur.echec(journal, "panne %s", "C") == 1
    assert caplog.records[0].levelno == logging.WARNING, (
        "le succès n'a pas remis le décompte à zéro : le compteur d'échecs "
        "CONSÉCUTIFS est devenu un compteur d'échecs tout court."
    )


def test_le_message_DIT_combien_de_fois(caplog):
    """Lire « échec consécutif n°3 » évite de compter les lignes du journal."""
    compteur = CompteurEchecs("relève", seuil=3)
    journal = logging.getLogger("essai_message")
    with caplog.at_level(logging.WARNING, logger="essai_message"):
        for _ in range(3):
            compteur.echec(journal, "panne : %s", "boom")
    dernier = caplog.records[-1]
    assert dernier.levelno == logging.ERROR
    assert "n°3" in dernier.getMessage()
    assert "relève" in dernier.getMessage()
    assert "boom" in dernier.getMessage(), "l'argument d'origine a été perdu"


def test_la_releve_remet_bien_le_compteur_a_zero_sur_un_SUCCES():
    """Le branchement, pas seulement la primitive : `relever` appelle-t-il `succes` ?

    C'est l'appel qu'on oublie — le module ne peut pas le deviner, et son absence
    ne se voit qu'au bout de trois pannes espacées.
    """
    import inspect

    from app.utils.courriel_boite import relever

    source = inspect.getsource(relever)
    assert ".succes()" in source, (
        "`relever` ne remet jamais le décompte à zéro : trois secousses espacées "
        "finiraient par déclencher l'alerte."
    )
    assert ".echec(" in source, "`relever` ne journalise plus l'échec par le compteur."
