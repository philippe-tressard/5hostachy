"""Un prestataire ou un contrat archivé a un ÉCRAN (#1538, 02/10/2026).

## Le constat

Archiver un prestataire posait `actif = False` par une route `DELETE`, et la
liste ne servait plus que les actifs : **aucun écran ne montrait un objet
archivé**. Archiver revenait à supprimer, sans le dire — l'icône était d'ailleurs
une corbeille. « Archiver ≠ supprimer » (`standards/11` §14) suppose que ce
qu'on range se retrouve, et se ressort.

## Ce que ce fichier tient

- la règle est **déclarée** dans `utils/archivage.REGLES`, comme celle des sept
  autres objets — `archivee` est calculé par le serveur, jamais par l'écran ;
- la liste sert les courants, `…/archives` ce qui est rangé — les autres
  lecteurs de la liste (formulaire d'affaire, reporting) n'en voient rien ;
- un seul geste, `PATCH …/archivage`, range ET ressort ;
- la route `DELETE` a disparu : elle portait le mot « supprimer » pour un geste
  qui ne supprimait rien.
"""

from __future__ import annotations

from datetime import date

from app.main import app
from app.models.core import ContratEntretien, Prestataire
from app.routers.prestataires import lister_contrats, lister_prestataires
from app.routers.prestataires_archivage import (
    Archivage,
    archiver_contrat,
    archiver_prestataire,
)
from app.utils.archivage import est_archivable
from tests.aides_base import compte


def _prestataire(session, nom: str, actif: bool = True) -> Prestataire:
    p = Prestataire(nom=nom, specialite="ascenseur", actif=actif)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def _contrat(session, prestataire_id: int, libelle: str, actif: bool = True) -> ContratEntretien:
    c = ContratEntretien(
        copropriete_id=1,
        prestataire_id=prestataire_id,
        libelle=libelle,
        date_debut=date(2026, 1, 1),
        actif=actif,
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def test_la_regle_est_declaree_et_lit_actif():
    """Un objet inactif est archivé ; un actif ne l'est jamais par le temps seul."""
    assert est_archivable("prestataire", Prestataire(nom="A", specialite="x", actif=False))
    assert not est_archivable("prestataire", Prestataire(nom="A", specialite="x", actif=True))
    assert est_archivable("contrat", ContratEntretien(libelle="C", prestataire_id=1, actif=False))
    assert not est_archivable(
        "contrat", ContratEntretien(libelle="C", prestataire_id=1, actif=True)
    )


def test_la_liste_sert_les_courants_et_a_part_les_archives(session):
    _prestataire(session, "Ascenseurs Durand")
    _prestataire(session, "Plomberie Martin", actif=False)

    courants = lister_prestataires(session, False)
    archives = lister_prestataires(session, True)

    assert [p.nom for p in courants] == ["Ascenseurs Durand"]
    assert [p.nom for p in archives] == ["Plomberie Martin"]
    assert not courants[0].archivee and archives[0].archivee


def test_un_geste_range_et_ressort_un_prestataire(session):
    cs = compte(session)
    p = _prestataire(session, "Ascenseurs Durand")

    archiver_prestataire(p.id, Archivage(archivee=True), session=session, _=cs)
    assert [x.nom for x in lister_prestataires(session, True)] == ["Ascenseurs Durand"]
    assert lister_prestataires(session, False) == []

    archiver_prestataire(p.id, Archivage(archivee=False), session=session, _=cs)
    assert lister_prestataires(session, True) == []


def test_un_geste_range_et_ressort_un_contrat(session):
    cs = compte(session)
    p = _prestataire(session, "Ascenseurs Durand")
    c = _contrat(session, p.id, "Entretien ascenseur")

    archiver_contrat(c.id, Archivage(archivee=True), session=session, _=cs)
    archives = lister_contrats(session, True)
    assert [x.libelle for x in archives] == ["Entretien ascenseur"]
    assert archives[0].archivee
    assert lister_contrats(session, False) == []

    archiver_contrat(c.id, Archivage(archivee=False), session=session, _=cs)
    assert [x.libelle for x in lister_contrats(session, False)] == ["Entretien ascenseur"]


def test_plus_aucune_route_delete_pour_archiver():
    """Le verbe disait « supprimer » pour un geste qui range : trois mots pour un."""
    for route in app.routes:
        chemin = getattr(route, "path", "")
        if chemin in ("/prestataires/{p_id}", "/prestataires/contrats/{c_id}"):
            assert "DELETE" not in getattr(route, "methods", set()), (
                f"DELETE {chemin} existe encore : archiver passe par PATCH …/archivage"
            )
