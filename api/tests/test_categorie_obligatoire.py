"""La catégorie d'une affaire est OBLIGATOIRE — aucun défaut ne la pose.

## Le besoin (21/09/2026, demandé à l'écran)

> « Catégorie : par défaut => Aucune catégorie de sélectionner (Actuellement :
>   Panne) »

Le formulaire ouvrait sur « 🛠️ Panne » cochée. Elle ne décore pas une carte :
c'est elle qui décide **de qui traite**, du circuit de suivi, et pour
« Étude & travaux » de l'entrée au tableau du conseil. Enregistrer sans y
toucher engageait donc quelqu'un d'autre, sans que personne sache le choix
manquant.

## 🔴 Pourquoi un test SERVEUR pour une demande d'écran

Retirer la présélection du formulaire seul aurait été décoratif :
`TicketCreate.categorie` portait `= "panne"`, donc un corps sans catégorie
repartait en panne — silencieusement, et par la porte même qu'on venait de
fermer. C'est la famille du « défaut qui survit au champ » : l'écran cesse de
proposer, le serveur continue de décider.

⚠️ Et la catégorie n'avait **aucune** liste blanche, contrairement au statut :
`body.categorie` allait jusqu'à `Ticket(categorie=…)`, dont SQLModel désactive
la validation (`table=True`). Une chaîne inventée — ou vide — entrait en base.

Le garde-fou d'écran est `front/scripts/check-choix-requis.mjs`, qui refuse
toute initialisation à une valeur de `CATEGORIES_TICKET`. Aucun des deux ne
suffit seul : l'un lit le formulaire, l'autre le contrat d'API.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.tickets import CategorieTicket
from app.schemas import TicketCreate

_MINIMUM = {"titre": "Fuite au 3e", "description": "De l'eau coule."}


def test_categorie_absente_refusee():
    """Aucun défaut : un corps sans catégorie ne passe plus."""
    with pytest.raises(ValidationError) as erreur:
        TicketCreate(**_MINIMUM)
    assert "categorie" in str(erreur.value)


def test_categorie_declaree_requise():
    """Le champ lui-même, et pas seulement une validation de circonstance."""
    champ = TicketCreate.model_fields["categorie"]
    assert champ.is_required(), "un défaut est réapparu sur `TicketCreate.categorie`"


@pytest.mark.parametrize("valeur", ["", "panne_du_voisin", "PANNE", "  "])
def test_categorie_inventee_refusee(valeur):
    """La chaîne vide comprise — c'est elle que le formulaire porte tant que
    l'auteur n'a pas choisi."""
    with pytest.raises(ValidationError):
        TicketCreate(**_MINIMUM, categorie=valeur)


@pytest.mark.parametrize("categorie", list(CategorieTicket))
def test_chaque_categorie_declaree_est_acceptee(categorie):
    """Dans les deux sens : le contrôle ne doit refuser aucune valeur réelle.

    Paramétré sur l'énumération, jamais sur une liste recopiée — sinon une
    catégorie ajoutée demain n'aurait aucun test.
    """
    corps = TicketCreate(**_MINIMUM, categorie=categorie.value)
    assert corps.categorie == categorie
