"""La fiche copropriété s'enregistre — y compris son échéance d'assurance.

`PATCH /copropriete` recevait `assurance_echeance` en **chaîne** (« 2026-12-17 »)
et l'affectait telle quelle à une colonne `date`. SQLAlchemy levait alors
« SQLite Date type only accepts Python date objects as input », et **toute la
fiche devenait inenregistrable** — y compris quand seul le nom du syndic avait
changé, puisque l'erreur tombe au `commit`.

Signalé à l'usage le 13/08/2026. Le défaut existait depuis l'ajout du champ :
personne n'avait retouché l'échéance, et un écran qui refuse d'enregistrer ne dit
pas *pourquoi* — le front affichait « Erreur lors de la sauvegarde ».

Ce fichier couvre la **classe** du défaut, pas seulement le cas rencontré : une
date valide, un champ vidé, une date illisible, et une modification qui ne touche
pas du tout à la date (le cas qui échouait sans qu'on comprenne le lien).
"""
from datetime import date

import pytest
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import Copropriete
from app.routers.copropriete import CoproprieteUpdate, update_copropriete


@pytest.fixture()
def copro() -> int:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for ligne in session.exec(select(Copropriete)).all():
            session.delete(ligne)
        session.commit()
        c = Copropriete(nom="Test", adresse="1 rue Test")
        session.add(c)
        session.commit()
        session.refresh(c)
        identifiant = c.id
    yield identifiant
    with Session(engine) as session:
        for ligne in session.exec(select(Copropriete)).all():
            session.delete(ligne)
        session.commit()


def _patch(**champs):
    """Appelle le router directement : c'est la couche où le défaut vivait."""
    with Session(engine) as session:
        return update_copropriete(
            body=CoproprieteUpdate(**champs), session=session, _=None
        )


def test_echeance_en_chaine_iso_est_convertie(copro):
    """Le cas qui échouait : une date saisie dans le formulaire."""
    lu = _patch(assurance_echeance="2026-12-17")
    assert lu.assurance_echeance == date(2026, 12, 17)

    with Session(engine) as session:
        stocke = session.get(Copropriete, copro)
        assert stocke.assurance_echeance == date(2026, 12, 17), (
            "la valeur doit être un `date` en base, pas une chaîne"
        )


def test_modifier_un_autre_champ_n_echoue_plus(copro):
    """Le symptôme le plus déroutant : changer le syndic échouait aussi.

    L'erreur tombe au `commit`, donc elle emportait la requête entière quel que
    soit le champ réellement modifié.
    """
    _patch(assurance_echeance="2026-12-17")
    lu = _patch(nom="Résidence du Parc")
    assert lu.nom == "Résidence du Parc"
    assert lu.assurance_echeance == date(2026, 12, 17), "l'échéance ne doit pas être perdue"


def test_echeance_videe_remet_a_neant(copro):
    """Effacer le champ dans le formulaire envoie une chaîne vide, pas `null`."""
    _patch(assurance_echeance="2026-12-17")
    lu = _patch(assurance_echeance="   ")
    assert lu.assurance_echeance is None


def test_echeance_illisible_repond_422_et_ne_corrompt_rien(copro):
    """Une saisie aberrante doit être refusée avec un message, pas avec un 500."""
    from fastapi import HTTPException

    _patch(assurance_echeance="2026-12-17")
    with pytest.raises(HTTPException) as erreur:
        _patch(assurance_echeance="17/12/2026")
    assert erreur.value.status_code == 422
    assert "AAAA-MM-JJ" in str(erreur.value.detail)

    with Session(engine) as session:
        assert session.get(Copropriete, copro).assurance_echeance == date(2026, 12, 17), (
            "un refus ne doit pas avoir écrasé la valeur précédente"
        )
