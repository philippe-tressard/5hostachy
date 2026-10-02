"""Le routeur `annonces_hall_sources` — ce qu'une affiche peut reprendre, et qui le demande (#1569).

Montée (`test_routeurs_montes`) mais jamais appelée par son nom : le relevé du
02/10/2026 comptait ce routeur parmi les modules qu'aucun test ne nomme. La
règle de FOND (ce qui est exclu : confidentiel, réservé au conseil, archivé…) est
tenue sans HTTP par `test_sources_affiche.py` ; ce fichier tient la PORTE :

1. un anonyme est refusé (401), un résident aussi (403) — une affiche de hall se
   prépare au conseil syndical ou à l'administration ;
2. le conseil et l'administration obtiennent la liste, dans la forme que lit
   l'écran, épinglés d'abord ;
3. le pré-remplissage rend **404 sans distinguer** « inexistant » de « fermé »
   (confidentiel) — dire lequel renseignerait sur un contenu protégé ;
4. les deux routes arrivent bien à CE routeur : `/annonces-hall/{annonce_id}`
   (route à paramètre, déclarée après) ne les capte pas.
"""

from __future__ import annotations

import json

import pytest
from sqlmodel import Session

from app.models.core import RoleUtilisateur, Ticket
from tests.aides_base import compte
from tests.aides_http import base_http, client_http

ROUTES = [
    "/annonces-hall/sources",
    "/annonces-hall/depuis/ticket/1",
]

_numero = [0]


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _affaire(moteur, titre="Réfection du hall", **champs) -> int:
    """Une affaire ouverte à tous, sur la résidence — ce qu'un hall peut reprendre."""
    _numero[0] += 1
    champs.setdefault("categorie", "espaces_verts")
    champs.setdefault("statut", "ouvert")
    champs.setdefault("perimetre_cible", json.dumps(["résidence"], ensure_ascii=False))
    with Session(moteur) as s:
        auteur = compte(s, prefixe="auteur")
        t = Ticket(
            numero=f"H-{_numero[0]:04d}",
            titre=titre,
            description="Texte de l'affaire.",
            auteur_id=auteur.id,
            **champs,
        )
        s.add(t)
        s.commit()
        return t.id


# ── La porte ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("route", ROUTES)
def test_un_anonyme_est_refuse(moteur, route):
    http, _ = client_http(moteur, None)
    assert http.get(route).status_code == 401


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("role", [RoleUtilisateur.résident, RoleUtilisateur.propriétaire])
def test_un_resident_ou_un_proprietaire_est_refuse(moteur, route, role):
    http, _ = client_http(moteur, role)
    assert http.get(route).status_code == 403


@pytest.mark.parametrize("role", [RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin])
def test_le_conseil_et_l_administration_passent(moteur, role):
    http, _ = client_http(moteur, role)
    assert http.get("/annonces-hall/sources").status_code == 200


# ── /sources ────────────────────────────────────────────────────────────────


def test_sans_aucune_affaire_la_liste_est_vide(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)
    assert http.get("/annonces-hall/sources").json() == []


def test_la_liste_a_la_forme_que_lit_l_ecran(moteur):
    ident = _affaire(moteur, "Réfection du hall")
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    [element] = http.get("/annonces-hall/sources").json()

    assert set(element) == {"cle", "type", "famille", "id", "titre", "date", "epingle"}
    assert element["cle"] == f"ticket:{ident}"
    assert (element["type"], element["id"], element["titre"]) == (
        "ticket",
        ident,
        "Réfection du hall",
    )
    assert element["famille"] == "Affaire"
    assert element["epingle"] is False


def test_une_actualite_se_presente_comme_une_actualite(moteur):
    _affaire(moteur, "Fête des voisins", categorie="actualite", statut="publie")
    http, _ = client_http(moteur, RoleUtilisateur.admin)

    [element] = http.get("/annonces-hall/sources").json()

    assert element["type"] == "ticket"
    assert element["famille"] == "Actualité"


def test_les_epingles_passent_avant_les_plus_recents(moteur):
    ancienne = _affaire(moteur, "Épinglée", epingle=True)
    recente = _affaire(moteur, "Plus récente")
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    ordre = [e["id"] for e in http.get("/annonces-hall/sources").json()]

    assert ordre == [ancienne, recente]


def test_une_affaire_confidentielle_n_est_jamais_proposee(moteur):
    _affaire(moteur, "Litige de voisinage", confidentiel=True)
    visible = _affaire(moteur, "Ouverte")
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    assert [e["id"] for e in http.get("/annonces-hall/sources").json()] == [visible]


def test_une_affaire_reservee_au_perimetre_n_est_pas_proposee(moteur):
    """Un hall se lit sans badge : ce que l'Accès referme sur un bâtiment n'y va pas."""
    _affaire(moteur, "Local technique", reserve_perimetre=True)
    http, _ = client_http(moteur, RoleUtilisateur.admin)

    assert http.get("/annonces-hall/sources").json() == []


# ── /depuis/{type}/{id} ─────────────────────────────────────────────────────


def test_le_prefill_d_une_affaire_rend_les_champs_du_formulaire(moteur):
    ident = _affaire(moteur, "Réfection du hall")
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    reponse = http.get(f"/annonces-hall/depuis/ticket/{ident}")

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert set(corps) == {"titre", "message", "perimetre_cible", "images"}
    assert corps["titre"] == "Réfection du hall"
    assert corps["message"] == "Texte de l'affaire."
    assert corps["perimetre_cible"] == ["résidence"]
    #  Les photos d'une affaire suivie sont des CONSTATS : on ne les reprend pas.
    assert corps["images"] == []


def test_le_prefill_d_une_actualite_rend_ses_images_sans_en_inventer(moteur):
    ident = _affaire(moteur, "Fête", categorie="actualite", statut="publie")
    http, _ = client_http(moteur, RoleUtilisateur.admin)

    reponse = http.get(f"/annonces-hall/depuis/ticket/{ident}")

    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["images"] == []


def test_un_type_inconnu_rend_404(moteur):
    ident = _affaire(moteur)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    for type_source in ("evenement", "publication", "n-importe-quoi"):
        reponse = http.get(f"/annonces-hall/depuis/{type_source}/{ident}")
        assert reponse.status_code == 404
        assert reponse.json()["detail"] == "Type d'élément inconnu"


def test_un_element_inexistant_rend_404(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    reponse = http.get("/annonces-hall/depuis/ticket/9999")

    assert reponse.status_code == 404
    assert reponse.json()["detail"] == "Élément introuvable ou non reprenable"


def test_inexistant_et_ferme_se_ressemblent_comme_deux_gouttes_d_eau(moteur):
    """🔴 Le point de sécurité : « fermé » ne se distingue pas d'« inexistant »."""
    ferme = _affaire(moteur, "Impayé du 3B", confidentiel=True)
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    sur_ferme = http.get(f"/annonces-hall/depuis/ticket/{ferme}")
    sur_absent = http.get("/annonces-hall/depuis/ticket/9999")

    assert (sur_ferme.status_code, sur_ferme.json()) == (sur_absent.status_code, sur_absent.json())
    assert sur_ferme.status_code == 404


@pytest.mark.parametrize(
    "champs",
    [
        {"confidentiel": True},
        {"reserve_perimetre": True},
        {"public_cible": json.dumps(["conseil_syndical"])},
        {"categorie": "nuisance"},  # défaut « Résident concerné » : fermé sans choix du conseil
    ],
    ids=["confidentiel", "reserve-perimetre", "reserve-conseil", "defaut-ferme"],
)
def test_un_contenu_qui_n_est_pas_reprenable_rend_404(moteur, champs):
    ident = _affaire(moteur, **champs)
    http, _ = client_http(moteur, RoleUtilisateur.admin)

    assert http.get(f"/annonces-hall/depuis/ticket/{ident}").status_code == 404


def test_une_affaire_annulee_n_est_pas_reprenable(moteur):
    """Une affaire annulée a quitté le fil : l'affiche ne la reprend pas."""
    ident = _affaire(moteur, statut="annulé")
    http, _ = client_http(moteur, RoleUtilisateur.conseil_syndical)

    assert http.get(f"/annonces-hall/depuis/ticket/{ident}").status_code == 404
    assert ident not in [e["id"] for e in http.get("/annonces-hall/sources").json()]
