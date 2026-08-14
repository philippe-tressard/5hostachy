"""Deux clés, deux défauts, et la même décision partout.

Ce fichier couvre trois choses qu'aucune relecture ne garantit :

1. **La décision d'envoi** — qui reçoit quoi selon son bâtiment. Elle était lue à
   trois endroits (`email/__init__.py` deux fois, `utils/reponses.py`) avec
   chacun ses défauts : trois façons d'être en désaccord sur ce que l'utilisateur
   a demandé.
2. **La conversion des préférences existantes** (migration `0145`). Elle décide du
   consentement de chaque résident : une erreur se traduit soit par des e-mails
   non sollicités, soit par un silence que personne n'a demandé.
3. **L'accord des deux côtés** — le site coche des cases dont le serveur seul
   décide. Une clé recopiée de travers ne produirait aucune erreur : l'écran
   enregistrerait un réglage que le serveur ne lirait jamais.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from app.models.core import Utilisateur
from app.utils.preferences_mail import (
    AUTRES_BATIMENTS,
    DEFAUTS,
    MON_BATIMENT,
    lire,
    mail_autorise,
)

RACINE = Path(__file__).resolve().parents[2]


def _utilisateur(prefs: str | None = None, batiment_id: int | None = None) -> Utilisateur:
    u = Utilisateur(nom="X", prenom="Y", email="x@test.fr", batiment_id=batiment_id, actif=True)
    if prefs is not None:
        u.preferences_notifications = prefs
    return u


# ── Les défauts ───────────────────────────────────────────────────────────────

def test_les_defauts_sont_recevoir_le_sien_pas_les_autres():
    """Personne n'a consenti aux autres bâtiments : le défaut ne peut pas être oui."""
    assert DEFAUTS == {MON_BATIMENT: True, AUTRES_BATIMENTS: False}


def test_un_json_illisible_rend_les_defauts():
    """Une préférence règle un confort : sur une donnée abîmée, on n'ampute pas.

    C'est l'inverse exact d'une décision de visibilité, où un JSON corrompu
    REFUSE (`utils/visibility._codes_json_pour_acces`). Les deux sont volontaires :
    ici le mauvais côté de l'erreur serait de priver quelqu'un d'un e-mail qu'il
    avait demandé ; là-bas, d'ouvrir un contenu réservé.
    """
    for abime in ("{pas du json", "[]", "null", ""):
        assert lire(_utilisateur(abime)) == DEFAUTS, abime


# ── La décision ───────────────────────────────────────────────────────────────

def test_sans_batiment_connu_du_contenu_c_est_mon_batiment_qui_decide():
    """Rappel de mot de passe, validation de compte : ça s'adresse à moi."""
    coupe = json.dumps({MON_BATIMENT: False, AUTRES_BATIMENTS: True})
    assert mail_autorise(_utilisateur(), None) is True
    assert mail_autorise(_utilisateur(coupe), None) is False
    #  Un contenu à portée globale (aucun bâtiment visé) relève de la même règle.
    assert mail_autorise(_utilisateur(coupe), set()) is False


def test_le_contenu_de_mon_batiment_suit_ma_premiere_case(batiments):
    mien = _utilisateur(batiment_id=batiments[0])
    assert mail_autorise(mien, {batiments[0]}) is True

    coupe = _utilisateur(json.dumps({MON_BATIMENT: False, AUTRES_BATIMENTS: True}),
                         batiment_id=batiments[0])
    assert mail_autorise(coupe, {batiments[0]}) is False


def test_le_contenu_d_ailleurs_suit_la_seconde_case(batiments):
    """Décochée par défaut : le résident ne reçoit pas les autres bâtiments."""
    mien = _utilisateur(batiment_id=batiments[0])
    assert mail_autorise(mien, {batiments[2]}) is False

    accepte = _utilisateur(json.dumps({MON_BATIMENT: True, AUTRES_BATIMENTS: True}),
                           batiment_id=batiments[0])
    assert mail_autorise(accepte, {batiments[2]}) is True


def test_sans_batiment_de_rattachement_on_ne_coupe_rien(batiments):
    """Cas zéro : on ne peut pas dire que le contenu vient d'ailleurs."""
    inconnu = _utilisateur()
    assert mail_autorise(inconnu, {batiments[1]}) is True


# ── La conversion des préférences existantes ──────────────────────────────────

def _migration():
    chemin = RACINE / "api" / "alembic" / "versions" / "0145_notifications_deux_choix.py"
    if not chemin.is_file():
        pytest.fail(f"Migration introuvable : {chemin.name}")
    spec = importlib.util.spec_from_file_location("migration_0145", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qui_recevait_des_mails_continue_d_en_recevoir():
    ancien = json.dumps({"ticket_mail": False, "actu_mail": True,
                         "doc_mail": False, "communaute_mail": False,
                         "ticket_app": True})
    assert json.loads(_migration().convertir(ancien))[MON_BATIMENT] is True


def test_qui_avait_tout_coupe_reste_au_silence():
    ancien = json.dumps({"ticket_mail": False, "actu_mail": False,
                         "doc_mail": False, "communaute_mail": False})
    converti = json.loads(_migration().convertir(ancien))
    assert converti[MON_BATIMENT] is False


def test_les_autres_batiments_ne_sont_jamais_actives_d_office():
    """Le test qui compte : on n'invente le consentement de personne."""
    for ancien in (
        json.dumps({"ticket_mail": True, "actu_mail": True, "doc_mail": True, "communaute_mail": True}),
        json.dumps({"ticket_mail": False}),
        "{}",
        "{pas du json",
    ):
        assert json.loads(_migration().convertir(ancien))[AUTRES_BATIMENTS] is False, ancien


def test_la_conversion_est_idempotente():
    """Un second passage ne doit rien retoucher."""
    deja = json.dumps({MON_BATIMENT: False, AUTRES_BATIMENTS: True})
    assert _migration().convertir(deja) is None


# ── L'accord du site et du serveur ────────────────────────────────────────────

def test_le_site_emploie_exactement_les_memes_cles():
    """Une clé recopiée de travers n'échouerait nulle part — elle mentirait."""
    source = RACINE / "front" / "src" / "lib" / "preferences.ts"
    if not source.is_file():
        pytest.fail(f"Fichier attendu introuvable : {source}")
    contenu = source.read_text(encoding="utf-8")

    for nom, valeur in (("MON_BATIMENT", MON_BATIMENT), ("AUTRES_BATIMENTS", AUTRES_BATIMENTS)):
        motif = rf"export const {nom} = '([^']+)'"
        trouve = re.search(motif, contenu)
        assert trouve, f"{nom} introuvable dans preferences.ts"
        assert trouve.group(1) == valeur, f"{nom} : « {trouve.group(1)} » ≠ « {valeur} »"

    #  Et les défauts, qui décident de ce que voit un compte neuf.
    assert re.search(rf"\[MON_BATIMENT\]:\s*{str(DEFAUTS[MON_BATIMENT]).lower()}", contenu)
    assert re.search(rf"\[AUTRES_BATIMENTS\]:\s*{str(DEFAUTS[AUTRES_BATIMENTS]).lower()}", contenu)
