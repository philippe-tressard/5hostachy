"""Un prestataire se CRÉE avec un contact joignable (#1229, arbitré le 24/09/2026).

« Contacts » devient une section obligatoire, donc dépliée, du formulaire
« Nouveau prestataire ». Ce qui est exigé, tranché par l'utilisateur :
**un contact avec un nom, et un téléphone OU un e-mail** — à la création
seulement : les fiches existantes se corrigent sans être bloquées.

La règle vit dans le schéma de CRÉATION, pour qu'aucun autre chemin (import,
appel direct) ne la contourne ; l'écran n'en montre que l'état.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.routers.prestataires_schemas import PrestataireCreate, PrestataireUpdate

BASE = {"nom": "Ascenseurs Durand", "specialite": "ascenseur"}


@pytest.mark.parametrize(
    "contacts",
    [
        None,
        [],
        [{"nom": "Durand"}],  # un nom, mais personne à joindre
        [{"telephone": "0600000000"}],  # un numéro, mais sans nom
        [{"nom": "  ", "email": "a@b.fr"}],  # un nom blanc n'est pas un nom
    ],
)
def test_une_creation_sans_contact_joignable_est_refusee(contacts):
    with pytest.raises(ValidationError, match="contact"):
        PrestataireCreate(**BASE, contacts=contacts)


@pytest.mark.parametrize(
    "contact",
    [{"nom": "Durand", "telephone": "0600000000"}, {"nom": "Durand", "email": "d@exemple.fr"}],
)
def test_un_nom_et_un_moyen_de_joindre_suffisent(contact):
    cree = PrestataireCreate(**BASE, contacts=[{"prenom": "", "nom": ""}, contact])
    assert len(cree.contacts) == 2


def test_la_modification_ne_l_exige_pas():
    """Les fiches existantes sans contact se corrigent sans être bloquées."""
    assert PrestataireUpdate(nom="Nouveau nom").contacts is None
    assert PrestataireUpdate(contacts=[]).contacts == []
