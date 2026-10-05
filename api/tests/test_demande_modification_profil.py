"""Une demande de modification de profil se rend de la même façon, créée ou relue (#1686).

## Le défaut

`POST /auth/me/demande-modification` rendait la ligne nue (`return demande`),
`GET /auth/me/demandes-modification` la même ligne PLUS le libellé du bâtiment
souhaité (`batiment_nom_souhaite`), composé à la main dans la seule liste. Une
demande tout juste déposée n'affichait donc pas « déménagement vers … » sur
l'écran du profil tant que la liste n'était pas rechargée.

## Ce que ce fichier vérifie

La réponse de la création porte `batiment_nom_souhaite`, et elle est
IDENTIQUE à la ligne que la liste rend pour la même demande : les deux routes
passent par une seule lecture.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from app.models.copropriete import Batiment, Copropriete
from app.models.core import RoleUtilisateur
from tests.aides_http import base_http, client_http


@pytest.fixture(name="moteur")
def moteur_fixture():
    with base_http() as moteur:
        yield moteur


def _batiment(moteur, numero: str = "3") -> int:
    with Session(moteur) as s:
        copro = Copropriete(nom="Témoin", adresse="1 rue du Témoin")
        s.add(copro)
        s.commit()
        bat = Batiment(numero=numero, copropriete_id=copro.id)
        s.add(bat)
        s.commit()
        return bat.id


def test_la_creation_rend_le_batiment_souhaite_comme_la_liste(moteur):
    bat_id = _batiment(moteur)
    http, _ = client_http(moteur, RoleUtilisateur.résident)

    cree = http.post(
        "/auth/me/demande-modification",
        json={"batiment_id_souhaite": bat_id, "motif": "Déménagement"},
    )
    assert cree.status_code == 201, cree.text
    assert cree.json().get("batiment_nom_souhaite") == "Bât. 3"

    liste = http.get("/auth/me/demandes-modification")
    assert liste.status_code == 200, liste.text
    assert liste.json() == [cree.json()]


def test_sans_batiment_souhaite_le_libelle_est_nul(moteur):
    http, _ = client_http(moteur, RoleUtilisateur.résident)

    cree = http.post("/auth/me/demande-modification", json={"statut_souhaite": "locataire"})
    assert cree.status_code == 201, cree.text
    assert "batiment_nom_souhaite" in cree.json()
    assert cree.json()["batiment_nom_souhaite"] is None
    assert http.get("/auth/me/demandes-modification").json() == [cree.json()]
