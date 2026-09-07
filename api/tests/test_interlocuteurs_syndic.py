"""À qui s'adresse un e-mail envoyé au syndic (09/08/2026).

Le cabinet fonctionne en binôme : l'assistante de gestion supplée la gestionnaire
en son absence, et les deux partagent la même boîte. La formule d'appel de la
relance n'en nommait qu'une (« Madame Céline Mariette »). Elle nomme désormais
les deux, sans prénom.

**Les personnes sont choisies par leur FONCTION, jamais par leur nom.** C'est la
demande explicite de l'utilisateur, et c'est la seule forme qui survive à un
changement de personnel chez le syndic — ce qui arrive plus souvent qu'une
relecture du code.
"""
import pathlib

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import GenreCivilite, MembreSyndic
from app.utils.destinataires import formule_appel, interlocuteurs_syndic

_APP = pathlib.Path(__file__).resolve().parents[1] / "app"


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


def _membre(nom, fonction, *, prenom="X", genre=GenreCivilite.mme, ordre=0, principal=False):
    return MembreSyndic(genre=genre, prenom=prenom, nom=nom, fonction=fonction,
                        email="x@exemple.test", ordre=ordre, est_principal=principal)


def test_l_annuaire_reel_donne_la_formule_attendue(session):
    """Les intitulés sont ceux réellement saisis en production, casse comprise."""
    session.add_all([
        _membre("Mariette", "Gestionnaire de Copropriétés", prenom="Céline", ordre=0, principal=True),
        _membre("THAUVIN", "Assistante de gestion", prenom="Océane", ordre=1),
        _membre("belyn", "Comptable de copropriété", prenom="Agnès", ordre=2),
    ])
    session.commit()

    assert formule_appel(interlocuteurs_syndic(session)) == "Madame Mariette, Madame Thauvin"


def test_la_comptable_est_exclue(session):
    """Elle traite les appels de fonds, pas les signalements techniques."""
    session.add_all([
        _membre("Mariette", "Gestionnaire de copropriété", ordre=0),
        _membre("Belyn", "Comptable de copropriété", ordre=1),
    ])
    session.commit()
    assert [m.nom for m in interlocuteurs_syndic(session)] == ["Mariette"]


@pytest.mark.parametrize("fonction", [
    "Gestionnaire de Copropriétés", "gestionnaire de copropriete",
    "GESTIONNAIRE", "Assistante de gestion", "Assistant de gestion",
])
def test_les_intitules_sont_reconnus_quelle_que_soit_la_saisie(session, fonction):
    """Accents, majuscules et genre varient d'une ligne à l'autre : c'est tapé au
    clavier. Comparer sur la forme brute ne reconnaîtrait que l'orthographe du
    jour de la saisie."""
    session.add(_membre("Dupont", fonction))
    session.commit()
    assert len(interlocuteurs_syndic(session)) == 1


def test_l_ordre_de_l_annuaire_est_respecte(session):
    """La gestionnaire d'abord : c'est elle l'interlocutrice principale."""
    session.add_all([
        _membre("Thauvin", "Assistante de gestion", ordre=5),
        _membre("Mariette", "Gestionnaire de copropriété", ordre=1),
    ])
    session.commit()
    assert formule_appel(interlocuteurs_syndic(session)) == "Madame Mariette, Madame Thauvin"


def test_un_homme_est_appele_monsieur(session):
    session.add(_membre("Durand", "Gestionnaire de copropriété", genre=GenreCivilite.mr))
    session.commit()
    assert formule_appel(interlocuteurs_syndic(session)) == "Monsieur Durand"


def test_un_nom_a_particule_n_est_pas_recasse(session):
    """Une casse mixte porte peut-être une particule : on n'y touche pas.

    « de La Tour » retitré donnerait « De La Tour ». Seule une casse uniforme
    (tout en capitales, tout en minuscules) trahit une saisie machinale.
    """
    session.add(_membre("de La Tour", "Gestionnaire de copropriété"))
    session.commit()
    assert formule_appel(interlocuteurs_syndic(session)) == "Madame de La Tour"


def test_repli_si_aucune_fonction_ne_correspond(session):
    """Un intitulé inattendu ne doit pas produire une formule d'appel VIDE.

    Un e-mail qui commence par une virgule ne se remarque qu'une fois parti :
    on retombe sur le membre marqué principal.
    """
    session.add_all([
        _membre("Mariette", "Responsable de secteur", principal=True),
        _membre("Belyn", "Comptable de copropriété"),
    ])
    session.commit()
    assert formule_appel(interlocuteurs_syndic(session)) == "Madame Mariette"


def test_aucun_nom_de_personne_n_est_ecrit_en_dur_dans_le_code():
    """La demande explicite de l'utilisateur, vérifiée plutôt que promise.

    Le cabinet change de personnel ; l'annuaire est la seule source qui suive.
    Un nom en dur ne casse rien le jour où il est écrit — il devient faux
    silencieusement, des mois plus tard, dans un e-mail déjà parti.
    """
    fichiers = [
        f for f in sorted(_APP.rglob("*.py")) if "__pycache__" not in f.parts
    ]
    assert len(fichiers) >= 40, (
        f"Seulement {len(fichiers)} module(s) analysé(s) — portée du contrôle cassée."
    )
    #: Les personnes actuellement à l'annuaire. Ce test ne prétend pas détecter
    #: tout nom propre : il verrouille le cas concret qui a motivé la règle.
    interdits = ("Mariette", "Thauvin", "Belyn")
    fautifs = [
        f"{f.relative_to(_APP).as_posix()} → {nom}"
        for f in fichiers
        for nom in interdits
        if nom in f.read_text(encoding="utf-8")
    ]
    assert not fautifs, (
        "Des noms de personnes du syndic sont écrits en dur dans le code : "
        f"{fautifs}. Les lire dans l'annuaire par leur FONCTION "
        "(`interlocuteurs_syndic`)."
    )
