"""Ce que l'écran Admin → Emails ÉCRIT sur un modèle (#852).

Deux gestes, un seul fichier : ils partagent les mêmes doublures et le même
sujet — ce qu'une session admin peut faire subir à un modèle en base.

## 1. Un modèle illisible ne s'enregistre pas

## Pourquoi le refus, et pas une alerte du lendemain

Le corps d'un modèle se saisit à la main dans un `<textarea>`, en Jinja. Un
`{% endif %}` de trop, un `{%` non refermé, et le modèle ne se rend plus.

Rien ne le disait. Pas à l'enregistrement — la route acceptait tout. Pas à
l'envoi non plus : `send_email` capture toute exception et n'enregistre l'échec
que dans `historique_email`, derrière une session admin. Le message cessait
simplement de partir.

Le contrôle quotidien de #850 finit par le voir, mais il le lisait comme un écart
de variables et affirmait une cause fausse. Et surtout : découvrir le lendemain
matin, par un e-mail d'alerte, une faute de frappe faite la veille n'a aucune
commune mesure avec la refuser pendant que la personne est **devant** le texte,
avec le caractère fautif que Jinja lui indique.

C'est la règle du socle : un garde-fou vaut mieux à l'endroit du geste
(`standards/05`).

## 2. Un modèle se remet par défaut SEUL

Seule la remise à zéro **globale** existait. Réparer le modèle cassé d'un
caractère imposait donc de détruire les textes choisis pour les vingt-trois
autres : un remède qu'on n'applique pas, et le défaut reste alors en place — le
contrôle quotidien signale, et personne ne peut agir.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers.admin.communications import update_modele_email


class _Modele:
    def __init__(self, sujet: str, corps: str):
        self.id = 1
        self.code = "compte_active"
        self.sujet = sujet
        self.corps_html = corps
        self.intention = "information"
        self.actif = True
        self.modifie_le = None
        self.modifie_par_id = None


class _Utilisateur:
    id = 42


class _Session:
    """Une session qui rend LE modèle, et note ce qui a été enregistré."""

    def __init__(self, modele):
        self._modele = modele
        self.commits = 0

    def get(self, _classe, _id):
        return self._modele

    def add(self, _objet):
        pass

    def commit(self):
        self.commits += 1

    def refresh(self, _objet):
        pass


def _modifier(payload, modele=None):
    modele = modele or _Modele("Objet", "<p>Bonjour {{ destinataire.prenom }}</p>")
    session = _Session(modele)
    return update_modele_email(1, payload, session, _Utilisateur()), session, modele


def test_un_CORPS_illisible_est_REFUSE_et_rien_n_est_enregistre():
    """🔴 Le cas réel : le texte est accepté, et le message ne part plus."""
    with pytest.raises(HTTPException) as leve:
        _modifier({"corps_html": "<p>{% if x %}Bonjour</p>"})

    assert leve.value.status_code == 422
    assert "corps_html" in leve.value.detail
    assert "invalide" in leve.value.detail.lower()


def test_un_OBJET_illisible_est_REFUSE_lui_aussi():
    """L'objet est un gabarit à part entière, rendu par le même moteur."""
    with pytest.raises(HTTPException) as leve:
        _modifier({"sujet": "{% for x in %}"})
    assert leve.value.status_code == 422
    assert "sujet" in leve.value.detail


def test_le_modele_n_est_PAS_modifie_par_un_refus():
    """Un refus laisse la ligne intacte : l'ancien message continue de partir."""
    modele = _Modele("Objet", "<p>Bonjour</p>")
    with pytest.raises(HTTPException):
        _modifier({"corps_html": "{% if %}"}, modele)
    assert modele.corps_html == "<p>Bonjour</p>"


def test_une_modification_VALIDE_passe_toujours():
    """🔴 Le cas zéro : un contrôle qui refuse tout ne protège plus rien.

    Sans lui, remplacer la validation par un `raise` inconditionnel laisserait
    les trois tests ci-dessus verts.
    """
    _resultat, session, modele = _modifier({"corps_html": "<p>{{ destinataire }}</p>"})
    assert modele.corps_html == "<p>{{ destinataire }}</p>"
    assert session.commits == 1


def test_modifier_la_seule_INTENTION_ne_relit_pas_un_corps_deja_en_base():
    """Une ligne dont le corps serait déjà cassé reste modifiable par ailleurs.

    Le contrôle porte sur ce que la requête ÉCRIT. Refuser ici bloquerait la
    seule voie de sortie : l'écran servirait à réparer, et refuserait d'agir.
    """
    modele = _Modele("Objet", "{% if x %}")
    _resultat, session, modele = _modifier({"intention": "information"}, modele)
    assert session.commits == 1


# ── 2. Remettre UN modèle par défaut ─────────────────────────────────────────

from app.routers.admin.communications import (  # noqa: E402
    _remettre_par_defaut,
    reinitialiser_un_modele_email,
)
from app.seed import EMAIL_TEMPLATES, INTENTIONS_PAR_MODELE  # noqa: E402


def _du_depot(code: str):
    _c, _l, sujet, corps, _d = next(t for t in EMAIL_TEMPLATES if t[0] == code)
    return sujet, corps


def test_remettre_UN_modele_par_defaut_rend_le_texte_du_code():
    sujet, corps = _du_depot("compte_active")
    modele = _Modele("Objet bricolé", "<p>corps bricolé</p>")
    session = _Session(modele)

    reinitialiser_un_modele_email(1, session, _Utilisateur())

    assert modele.sujet == sujet
    assert modele.corps_html == corps
    assert session.commits == 1


def test_elle_remet_AUSSI_l_intention():
    """Sinon un modèle réinitialisé garde un bandeau modifié sur un corps d'origine."""
    modele = _Modele("Objet", "<p>corps</p>")
    modele.intention = "action_requise"
    _remettre_par_defaut(_Session(modele), modele, 42)
    assert modele.intention == INTENTIONS_PAR_MODELE["compte_active"]


def test_un_modele_INCONNU_du_code_n_a_rien_a_quoi_revenir():
    """Créé à la main, ou disparu du seed : le dire, plutôt que l'écraser de vide."""
    modele = _Modele("Objet", "<p>corps</p>")
    modele.code = "modele_maison"
    assert _remettre_par_defaut(_Session(modele), modele, 42) is False
    assert modele.corps_html == "<p>corps</p>"

    with pytest.raises(HTTPException) as leve:
        reinitialiser_un_modele_email(1, _Session(modele), _Utilisateur())
    assert leve.value.status_code == 422


def test_un_modele_ILLISIBLE_se_repare_par_ce_chemin():
    """🔴 Le cas qui a motivé la route : la seule sortie d'un Jinja cassé.

    L'enregistrement refuse le texte invalide — encore faut-il pouvoir remplacer
    celui qui est déjà en base sans détruire les vingt-trois autres modèles.
    """
    sujet, corps = _du_depot("compte_active")
    modele = _Modele("Objet", "<p>{% if x %}cassé</p>")
    reinitialiser_un_modele_email(1, _Session(modele), _Utilisateur())
    assert modele.corps_html == corps
    assert modele.sujet == sujet
