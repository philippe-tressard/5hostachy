"""La marque « rédigé avec l'assistant IA » — neuf tables, une notion (#985).

## Ce que ce test protège

1. **Chaque entité qui porte une section Description porte la colonne**, par
   le mixin — pas par une déclaration recopiée.
2. **La marque ne s'écrit que dans UN sens** : `marquer()` pose `True`, ignore
   `False` et `None`. Une retouche à la main n'efface pas la contribution.
3. **Les schémas la transportent** aux trois moments — création, correction,
   lecture — sur les neuf circuits. Une colonne qui voyage sans être posée
   par un formulaire est le défaut de `standards/06` §5 bis ; le contrôle
   symétrique est ici : une colonne posée qu'un schéma ne transporterait pas
   n'arriverait jamais en base.
"""

from __future__ import annotations

import pytest

from app.utils.assiste_ia import (
    AssisteIACorrection,
    AssisteIAEntree,
    AssisteIAMixin,
    AssisteIASortie,
    marquer,
)


def _modeles():
    from app.models.communaute import Idee, PetiteAnnonce, Sondage
    from app.models.core import Publication, PublicationEvolution, Ticket, TicketEvolution

    return [
        Ticket,
        Publication,
        TicketEvolution,
        PublicationEvolution,
        Sondage,
        Idee,
        PetiteAnnonce,
    ]


def test_les_entites_portent_la_colonne_par_le_mixin():
    #  L'événement est parti le 23/09/2026 (#1092) : c'est une affaire.
    for modele in _modeles():
        assert issubclass(modele, AssisteIAMixin), modele.__name__
        assert "assiste_ia" in modele.model_fields, modele.__name__
        assert modele.model_fields["assiste_ia"].default is False


class _Objet:
    assiste_ia = False


class _Corps:
    def __init__(self, valeur):
        self.assiste_ia = valeur


@pytest.mark.parametrize("valeur, attendu", [(True, True), (False, False), (None, False)])
def test_la_marque_se_pose_et_ne_se_retire_pas(valeur, attendu):
    o = _Objet()
    marquer(o, _Corps(valeur))
    assert o.assiste_ia is attendu


def test_un_faux_n_efface_pas_une_marque_posee():
    o = _Objet()
    o.assiste_ia = True
    marquer(o, _Corps(False))
    assert o.assiste_ia is True


def test_les_schemas_transportent_la_marque_sur_les_neuf_circuits():
    from app.routers.annonces import AnnonceCreate, AnnonceUpdate
    from app.routers.idees import IdeeCreate, IdeeUpdate
    from app.routers.sondages.commun import SondageCreate, SondageRead, SondageUpdate

    #  Les quatre schémas des publications sont partis le 23/09/2026 : une
    #  actualité est une affaire (#1091), elle passe par ceux des tickets.
    from app.schemas import (
        TicketCreate,
        TicketEvolutionCreate,
        TicketEvolutionUpdate,
        TicketRead,
        TicketUpdate,
    )
    from app.schemas_communs import EvolutionLue

    creations = (
        TicketCreate,
        TicketEvolutionCreate,
        SondageCreate,
        IdeeCreate,
        AnnonceCreate,
    )
    corrections = (
        TicketUpdate,
        TicketEvolutionUpdate,
        SondageUpdate,
        IdeeUpdate,
        AnnonceUpdate,
    )
    lectures = (TicketRead, SondageRead)
    for s in creations:
        assert issubclass(s, AssisteIAEntree), s.__name__
    for s in corrections:
        assert issubclass(s, AssisteIACorrection), s.__name__
    for s in lectures:
        assert issubclass(s, AssisteIASortie), s.__name__
    #  Les fils lisent par `EvolutionLue`, qui n'importe rien du projet : le
    #  champ y est déclaré à la main, et ce test le garde d'accord avec le mixin.
    assert EvolutionLue.model_fields["assiste_ia"].default is False
    #  L'idée et l'annonce rendent le modèle (ou son `model_dump`) : la colonne
    #  du mixin sort d'elle-même.
