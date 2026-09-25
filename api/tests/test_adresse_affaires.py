"""Un courriel d'affaire part de l'adresse des affaires, et la réponse y revient (#1314).

## Pourquoi

Le `Reply-To` d'une affaire était `tickets+<jeton>@<domaine>` (#703) : le jeton
rattachait la réponse à son dossier. OVH n'achemine pas le sous-adressage — la
réponse du syndic partait dans le vide. Constaté le 05/09 (#754, qui a posé le
repli par le numéro du sujet), signalé de nouveau le 25/09/2026.

Arbitré : l'affaire part DE l'adresse des affaires (`smtp_from_affaires`,
réglée dans Paramétrage → SMTP — `affaire@5hostachy.fr`, un alias relevé par
IMAP), et la réponse y REVIENT. Le rattachement se fait par « Affaire #TK-… »
dans le sujet, qui marche déjà.
"""

from __future__ import annotations

from app.seed.emails import expediteur_du_modele
from app.utils.smtp import entete_reponse as _reply_to
from app.utils.smtp import adresse_expedition, adresses_a_tester

_CFG = {
    "smtp_from": "noreply@5hostachy.fr",
    "smtp_from_reponse": "contact@5hostachy.fr",
    "smtp_from_affaires": "affaire@5hostachy.fr",
}


def test_la_reponse_revient_a_l_adresse_des_affaires():
    assert _reply_to(_CFG, "c7a5d821b9a9d9c2ffe5132314af276b") == {
        "Reply-To": "affaire@5hostachy.fr"
    }


def test_aucun_reply_to_sous_adresse():
    """🔴 Le défaut exact : `tickets+<jeton>@` — OVH ne l'achemine pas."""
    for cfg in (_CFG, {k: v for k, v in _CFG.items() if k != "smtp_from_affaires"}):
        entete = _reply_to(cfg, "c7a5d821b9a9d9c2ffe5132314af276b")
        assert "+" not in entete["Reply-To"], entete


def test_l_affaire_part_de_l_adresse_des_affaires():
    genre = expediteur_du_modele("ticket_externe", jeton_reponse="abc")
    assert adresse_expedition(_CFG, genre) == "affaire@5hostachy.fr"


def test_sans_adresse_des_affaires_on_se_replie_sur_celle_des_reponses():
    """Une installation qui n'a pas encore réglé l'adresse n'envoie pas de nulle part."""
    cfg = {k: v for k, v in _CFG.items() if k != "smtp_from_affaires"}
    assert _reply_to(cfg, "abc") == {"Reply-To": "contact@5hostachy.fr"}
    genre = expediteur_du_modele("ticket_externe", jeton_reponse="abc")
    assert adresse_expedition(cfg, genre) == "contact@5hostachy.fr"
    assert _reply_to({"smtp_from": "noreply@5hostachy.fr"}, "abc") == {
        "Reply-To": "noreply@5hostachy.fr"
    }


def test_un_envoi_hors_affaire_ne_porte_pas_de_reply_to():
    assert _reply_to(_CFG, None) == {}


def test_le_bouton_tester_eprouve_aussi_l_adresse_des_affaires():
    """OVH peut refuser d'expédier sous un alias : le test SMTP doit l'essayer."""
    assert "affaire@5hostachy.fr" in adresses_a_tester(_CFG)
