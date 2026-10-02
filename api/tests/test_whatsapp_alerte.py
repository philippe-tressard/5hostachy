"""Prévenir un humain quand un message WhatsApp n'est pas arrivé — `whatsapp_alerte` (#1569, #1057).

Le module n'était nommé par aucun test. Il porte la CONDUITE à tenir sur un envoi
incertain (ne jamais rejouer, aller regarder le groupe), qui protège du doublon du
14/08/2026, et la promesse « ne lève jamais ». Les deux collaborateurs — l'adresse
du gestionnaire et l'envoi de l'alerte — sont remplacés par des espions : on lit ce
qui leur est demandé, rien ne part.

1. un envoi INCERTAIN : « vérifier le groupe », jamais « rien n'est parti » ni « renvoyez » sans condition ;
2. un ÉCHEC établi : rien n'est parti, le renvoi est sans risque ; la précision de l'appelant s'ajoute ;
3. la dernière erreur est toujours dite, « inconnue » à défaut ;
4. sans adresse de gestionnaire : rien n'est envoyé, un avertissement le dit ;
5. une panne de l'envoi ou de la lecture de l'adresse n'empêche JAMAIS d'enregistrer
   ce qui s'est passé : l'exception ne sort pas.
"""

from __future__ import annotations

import logging

import pytest

import app.utils.email as email_module
import app.utils.health_monitor as health_monitor
from app.utils.whatsapp import STATUT_ECHEC, STATUT_INCERTAIN
from app.utils.whatsapp_alerte import alerter_envoi

DESTINATAIRE = "gestion@exemple.test"


@pytest.fixture()
def envois(monkeypatch):
    """Les alertes qui PARTIRAIENT : `(destinataire, [constats])`."""
    partis: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        email_module, "get_site_manager_notification_email", lambda s: (DESTINATAIRE, {})
    )
    monkeypatch.setattr(
        health_monitor, "_send_alert", lambda to, issues, session: partis.append((to, issues))
    )
    return partis


def _alerter(statut, erreur="délai dépassé", **kw):
    alerter_envoi(None, "Encombrants", statut, erreur, **kw)


# ── Incertain ───────────────────────────────────────────────────────────────


def test_un_envoi_incertain_demande_d_aller_voir_le_groupe(envois):
    _alerter(STATUT_INCERTAIN)

    [(to, [constat])] = envois
    assert to == DESTINATAIRE
    assert "« Encombrants »" in constat
    assert "peut-être arrivé" in constat
    assert "Vérifier le groupe WhatsApp" in constat
    assert "Aucun rejeu automatique" in constat


def test_un_envoi_incertain_ne_dit_pas_que_rien_n_est_parti(envois):
    """Le doute n'est pas un échec : dire « rien n'est parti » ferait renvoyer un doublon."""
    _alerter(STATUT_INCERTAIN)

    [(_, [constat])] = envois
    assert "Rien n'est parti" not in constat
    assert "sans risque" not in constat


# ── Échec établi ────────────────────────────────────────────────────────────


def test_un_echec_dit_que_rien_n_est_parti_et_que_le_renvoi_est_sans_risque(envois):
    _alerter(STATUT_ECHEC)

    [(_, [constat])] = envois
    assert "non envoyé" in constat
    assert f"Statut : {STATUT_ECHEC}" in constat
    assert "Rien n'est parti" in constat
    assert "sans risque" in constat


def test_la_precision_de_l_appelant_complete_le_constat_d_echec(envois):
    _alerter(STATUT_ECHEC, precision=" Rattrapage possible jusqu'à 18 h.")

    [(_, [constat])] = envois
    assert "non envoyé. Rattrapage possible jusqu'à 18 h." in constat


# ── La dernière erreur ──────────────────────────────────────────────────────


@pytest.mark.parametrize("statut", [STATUT_ECHEC, STATUT_INCERTAIN])
def test_la_derniere_erreur_est_toujours_dite(envois, statut):
    _alerter(statut, erreur="réponse 500 du bridge")

    [(_, [constat])] = envois
    assert constat.endswith("Dernière erreur : réponse 500 du bridge")


@pytest.mark.parametrize("erreur", [None, ""])
def test_sans_erreur_connue_le_constat_ecrit_inconnue(envois, erreur):
    _alerter(STATUT_ECHEC, erreur=erreur)

    [(_, [constat])] = envois
    assert constat.endswith("Dernière erreur : inconnue")


def test_un_seul_constat_par_alerte(envois):
    _alerter(STATUT_ECHEC)
    _alerter(STATUT_INCERTAIN)

    assert [len(issues) for _, issues in envois] == [1, 1]


# ── Sans destinataire ───────────────────────────────────────────────────────


def test_sans_adresse_de_gestionnaire_rien_n_est_envoye_et_un_avertissement_le_dit(
    monkeypatch, caplog
):
    envoyes = []
    monkeypatch.setattr(email_module, "get_site_manager_notification_email", lambda s: ("", {}))
    monkeypatch.setattr(health_monitor, "_send_alert", lambda *a: envoyes.append(a))

    with caplog.at_level(logging.WARNING, logger="app.utils.whatsapp_alerte"):
        _alerter(STATUT_ECHEC, erreur="timeout")

    assert envoyes == []
    assert "pas d'email admin configuré" in caplog.text
    assert "Encombrants" in caplog.text and "timeout" in caplog.text


# ── Ne lève jamais ──────────────────────────────────────────────────────────


def test_une_panne_de_l_envoi_n_empeche_pas_d_enregistrer_ce_qui_s_est_passe(monkeypatch, caplog):
    monkeypatch.setattr(
        email_module, "get_site_manager_notification_email", lambda s: (DESTINATAIRE, {})
    )

    def _en_panne(*_):
        raise ConnectionError("SMTP injoignable")

    monkeypatch.setattr(health_monitor, "_send_alert", _en_panne)

    with caplog.at_level(logging.WARNING, logger="app.utils.whatsapp_alerte"):
        _alerter(STATUT_INCERTAIN)  # ne lève pas

    assert "Alerte d'envoi WhatsApp non partie (Encombrants)" in caplog.text
    assert "SMTP injoignable" in caplog.text


def test_une_lecture_impossible_de_l_adresse_n_empeche_pas_non_plus(monkeypatch, caplog):
    def _illisible(_):
        raise RuntimeError("base verrouillée")

    monkeypatch.setattr(email_module, "get_site_manager_notification_email", _illisible)

    with caplog.at_level(logging.WARNING, logger="app.utils.whatsapp_alerte"):
        _alerter(STATUT_ECHEC)  # ne lève pas

    assert "base verrouillée" in caplog.text
