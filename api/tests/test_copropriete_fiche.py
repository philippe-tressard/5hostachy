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


def test_les_deux_decomptes_de_lots_sont_independants(copro):
    """Les deux chiffres de la fiche ANAH ne se déduisent pas l'un de l'autre.

    La fiche du registre national en porte deux : le total (caves et parkings
    compris) et les seuls lots d'habitation, commerces et bureaux — relevé réel
    sur la résidence, 195 et 63. L'application n'avait qu'un champ, si bien que le
    chiffre saisi ne disait pas lequel il était et que le produit annonçait une
    taille fausse du simple au triple.

    Ce test verrouille l'indépendance : écrire l'un ne doit pas toucher l'autre.
    Le rapport entre les deux dépend du nombre de caves et de parkings, propre à
    chaque copropriété — le déduire serait inventer une mesure.
    """
    lu = _patch(nb_lots_total=195, nb_lots_principaux=63)
    assert (lu.nb_lots_total, lu.nb_lots_principaux) == (195, 63)

    lu = _patch(nb_lots_total=196)
    assert lu.nb_lots_principaux == 63, "modifier le total a écrasé les lots principaux"


def test_un_seul_decompte_renseigne_reste_valide(copro):
    """Une copropriété peut n'en connaître qu'un — on n'invente pas l'autre.

    Cas zéro du couple (`standards/04-fiabilite-des-controles.md` §2) : le champ
    absent reste vide, et l'écran n'affiche que celui qu'il a.
    """
    lu = _patch(nb_lots_principaux=63)
    assert lu.nb_lots_principaux == 63
    assert lu.nb_lots_total is None, "le total a été déduit alors que personne ne le sait"
