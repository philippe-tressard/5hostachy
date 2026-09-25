"""La fiche d'un prestataire : contact FACULTATIF, adresse et description (#1327).

## Revirement du 25/09/2026

#1229 (24/09) exigeait à la création « un contact avec un nom, et un téléphone
ou un e-mail ». Arbitré à l'écran le lendemain, capture à l'appui : « le contact
ne doit pas être obligatoire ». La fiche gagne en même temps :

- l'**adresse de l'entreprise**, facultative, dans la section Contacts ;
- une **description** (section rouverte, avec l'assistant ✨ comme partout) —
  donc la marque `assiste_ia`, que toute entité à Description porte.

Ce fichier garde son nom : c'est l'histoire de la même règle, dans l'autre sens.
"""

from __future__ import annotations

import pytest

from app.models.prestataires import Prestataire
from app.routers.prestataires_schemas import PrestataireCreate, PrestataireRead, PrestataireUpdate
from app.utils.assiste_ia import AssisteIAMixin

BASE = {"nom": "Ascenseurs Durand", "specialite": "ascenseur"}


@pytest.mark.parametrize(
    "contacts",
    [None, [], [{"nom": "Durand"}], [{"telephone": "0600000000"}]],
)
def test_une_creation_sans_contact_joignable_est_acceptee(contacts):
    """🔴 Cas zéro : ces quatre créations étaient refusées (422) depuis #1229."""
    cree = PrestataireCreate(**BASE, contacts=contacts)
    assert cree.nom == "Ascenseurs Durand"


def test_l_adresse_et_la_description_voyagent_aux_trois_moments():
    cree = PrestataireCreate(
        **BASE, adresse="12 rue des Lilas\n75012 Paris", description="<p>Réactif.</p>"
    )
    assert cree.adresse == "12 rue des Lilas\n75012 Paris"
    assert cree.description == "<p>Réactif.</p>"
    assert PrestataireUpdate(adresse="ailleurs").adresse == "ailleurs"
    lu = PrestataireRead(
        id=1, nom="X", specialite="y", actif=True, adresse="a", description="d", assiste_ia=True
    )
    assert (lu.adresse, lu.description, lu.assiste_ia) == ("a", "d", True)


def test_le_prestataire_porte_la_marque_de_l_assistant_par_le_mixin():
    assert issubclass(Prestataire, AssisteIAMixin)
    assert Prestataire.model_fields["assiste_ia"].default is False
    for champ in ("adresse", "description"):
        assert champ in Prestataire.model_fields, champ


def test_une_correction_sans_l_assistant_n_efface_pas_la_marque():
    assert PrestataireUpdate(nom="Nouveau nom").assiste_ia is None
    assert PrestataireCreate(**BASE).assiste_ia is False
