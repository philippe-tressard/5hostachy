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


def _heritiers(base: type) -> list[type]:
    """Toutes les classes qui héritent de `base`, à toute profondeur."""
    return [c for s in base.__subclasses__() for c in (s, *_heritiers(s))]


#: Le nombre de tables marquées sous lequel la dérivation ne voit plus tout.
PLANCHER_TABLES = 9


def _modeles() -> list[type]:
    """Les TABLES qui portent la colonne — dérivées du mixin, jamais listées.

    🔴 Jusqu'au 30/09/2026 (#1496), une liste écrite à la main : six tables sur
    neuf. `AnnonceHall`, `Evenement` et `EvenementEvolution` héritaient du mixin
    sans que ce test les regarde.
    """
    #  `app.models.core`, pas `app.models` : c'est `core` qui charge TOUS les
    #  modules de modèles (`test_modeles_enregistres.py`) — `app.models` seul
    #  n'en voyait que deux tables sur neuf.
    import app.models.core  # noqa: F401

    tables = {c for c in _heritiers(AssisteIAMixin) if getattr(c, "__table__", None) is not None}
    assert len(tables) >= PLANCHER_TABLES, (
        f"{len(tables)} table(s) héritent du mixin (plancher {PLANCHER_TABLES}) : la "
        "dérivation ne voit plus les modèles — un module n'est plus importé ?"
    )
    return sorted(tables, key=lambda c: c.__name__)


def _schemas_de_creation() -> dict[str, type]:
    """Les schémas d'entrée qui transportent la marque, par nom — dérivés eux aussi."""
    import app.main  # noqa: F401 — monte chaque routeur, donc déclare chaque schéma

    return {c.__name__: c for c in _heritiers(AssisteIAEntree)}


#: Le schéma de création d'une table, quand il ne s'appelle pas `<Table>Create`.
CREATION_DE = {"PetiteAnnonce": "AnnonceCreate"}

#: Les tables marquées que RIEN ne crée plus — donc sans schéma de création. Le
#: dernier test vérifie qu'aucun code de `app/` ne les construit : le jour où
#: l'une se crée de nouveau, son schéma doit transporter la marque.
SANS_CREATION = {
    "Evenement": "le calendrier est devenu une affaire (#1092) : la table n'est plus que lue",
    "EvenementEvolution": "le fil d'un événement, parti avec lui (#1092)",
}


def test_les_entites_portent_la_colonne_par_le_mixin():
    #  L'événement est devenu une affaire le 23/09/2026 (#1092), mais sa table
    #  hérite toujours du mixin : elle est lue ici comme les autres.
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
    from app.routers.annonces import AnnonceUpdate
    from app.routers.idees import IdeeUpdate
    from app.routers.sondages.commun import SondageRead, SondageUpdate

    #  Les quatre schémas des publications sont partis le 23/09/2026 : une
    #  actualité est une affaire (#1091), elle passe par ceux des tickets.
    from app.schemas import TicketEvolutionUpdate, TicketRead, TicketUpdate
    from app.schemas_communs import EvolutionLue

    #  Les CRÉATIONS sont dérivées : `test_chaque_table_marquee_a_son_schema_de_creation`.
    corrections = (
        TicketUpdate,
        TicketEvolutionUpdate,
        SondageUpdate,
        IdeeUpdate,
        AnnonceUpdate,
    )
    lectures = (TicketRead, SondageRead)
    for s in corrections:
        assert issubclass(s, AssisteIACorrection), s.__name__
    for s in lectures:
        assert issubclass(s, AssisteIASortie), s.__name__
    #  Les fils lisent par `EvolutionLue`, qui n'importe rien du projet : le
    #  champ y est déclaré à la main, et ce test le garde d'accord avec le mixin.
    assert EvolutionLue.model_fields["assiste_ia"].default is False
    #  L'annonce rend le modèle (ou son `model_dump`) : la colonne du mixin sort
    #  d'elle-même. L'idée, non : sa liste était un dictionnaire écrit à la main et
    #  l'oubliait (#1660) — `IdeeRead` la lit désormais sur le modèle, et
    #  `test_idee_lecture.py` le vérifie.


def test_chaque_table_marquee_a_son_schema_de_creation():
    """Une colonne qu'aucun formulaire ne pose n'arrive jamais en base : à chaque
    table héritière du mixin, un schéma de création héritier d'`AssisteIAEntree`
    — les deux listes DÉRIVÉES, rapprochées par le nom (#1496)."""
    schemas = _schemas_de_creation()
    manquants = [
        f"{m.__name__} → {CREATION_DE.get(m.__name__, m.__name__ + 'Create')}"
        for m in _modeles()
        if m.__name__ not in SANS_CREATION
        and CREATION_DE.get(m.__name__, f"{m.__name__}Create") not in schemas
    ]
    assert not manquants, (
        "Table marquée dont le schéma de création ne transporte pas `assiste_ia` "
        f"(ou porte un autre nom — le déclarer dans `CREATION_DE`) : {manquants}"
    )


def test_les_declarations_servent_encore():
    """`CREATION_DE` et `SANS_CREATION` ne nomment que des tables marquées, et
    une table « sans création » n'est construite nulle part dans `app/`."""
    import ast

    from tests.aides_sources import modules_app

    noms = {m.__name__ for m in _modeles()}
    mortes = sorted((set(CREATION_DE) | set(SANS_CREATION)) - noms)
    assert not mortes, f"déclaration(s) sur une table qui n'hérite plus du mixin : {mortes}"
    construites = sorted(
        f"{n.func.id} — app/{m.rel}:{n.lineno}"
        for m in modules_app()
        for n in ast.walk(m.arbre)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in SANS_CREATION
    )
    assert not construites, (
        f"table déclarée sans création, et pourtant construite : {construites} — "
        "son schéma de création doit transporter la marque"
    )
