"""Le pied de page se règle dans Admin › Site — ce que le serveur en garde (08/10/2026).

L'année de création et le texte libre s'ajoutent aux éléments masqués : ce que
le pied de page affiche se lit sans être connecté (`GET /config`), et le texte
libre, public, est borné à l'enregistrement. Le vrai client HTTP, la vraie
authentification ; seule la base est détournée.
"""

from __future__ import annotations

import pytest

from app.models.core import RoleUtilisateur
from app.utils.pied_de_page import PREFIXE_NOM_MAX, TEXTE_PIED_MAX
from tests.aides_http import base_http, client_http

_CLES = (
    "pied_de_page_masques",
    "pied_de_page_annee_debut",
    "pied_de_page_texte",
    "pied_de_page_ordre",
    "pied_de_page_prefixe_nom",
)


@pytest.fixture
def moteur():
    with base_http() as m:
        yield m


def test_le_reglage_du_pied_de_page_se_lit_sans_etre_connecte(moteur):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    valeurs = dict(
        zip(
            _CLES,
            ("version", "2026", "Résidence gérée par son conseil", "annee,source", "Résidence"),
        )
    )
    assert admin.put("/config", json=valeurs).status_code == 200
    public = client_http(moteur, None)[0].get("/config").json()
    assert {cle: public.get(cle) for cle in _CLES} == valeurs


def test_le_texte_libre_est_borne_et_tient_sur_une_ligne(moteur):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    assert (
        admin.put("/config", json={"pied_de_page_texte": "a\n  b " + "x" * 500}).status_code == 200
    )
    texte = client_http(moteur, None)[0].get("/config").json()["pied_de_page_texte"]
    assert texte.startswith("a b x")
    assert len(texte) == TEXTE_PIED_MAX


def test_le_prefixe_du_nom_est_borne_et_tient_sur_une_ligne(moteur):
    admin, _ = client_http(moteur, RoleUtilisateur.admin)
    saisie = " Rési\ndence " + "y" * 99
    assert admin.put("/config", json={"pied_de_page_prefixe_nom": saisie}).status_code == 200
    prefixe = client_http(moteur, None)[0].get("/config").json()["pied_de_page_prefixe_nom"]
    assert prefixe.startswith("Rési dence y")
    assert len(prefixe) == PREFIXE_NOM_MAX
