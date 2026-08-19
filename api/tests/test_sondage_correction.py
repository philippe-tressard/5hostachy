"""Corriger un sondage sans détruire ce qui a déjà été exprimé (#467).

Avant ce lot, `PATCH /sondages/{id}` existait et **aucun écran ne l'appelait**.
Corriger une faute de frappe dans une question imposait donc de supprimer et de
recréer — ce qui perd **les votes déjà exprimés**, sans que personne soit prévenu :
les votants ne le savent pas, ils ne sont pas re-sollicités (la notification de
création n'est partie qu'une fois), et le sondage recréé repart à zéro. Son
résultat sera lu comme légitime alors qu'il ne porte que sur les votants du second
tour.

Un sondage de copropriété sert à préparer une décision. Un résultat faussé par une
correction de forme n'est pas un désagrément d'interface.

## La frontière, tranchée par l'utilisateur le 19/08/2026

| Champ | Après le premier vote |
|---|---|
| question, description | corrigeable |
| **libellé** d'une option | corrigeable |
| **ajout / retrait** d'une option | 🔴 impossible |
| date de clôture | **reculable**, jamais avançable |

La raison du point dur : un vote sur une option retirée n'a pas de repli honnête.
Le compter ailleurs fausse le résultat ; le supprimer efface l'expression de
quelqu'un sans le lui dire.

## Ce que ces tests vérifient, et pourquoi ils portent sur la FRONTIÈRE

Un test qui vérifierait « corriger la question marche » ne dit presque rien : c'est
le cas facile. Ce qui compte est ce que le serveur **refuse**, et qu'il refuse au
bon moment — avant le premier vote, un sondage se corrige librement ; après, il
engage des gens.

⚠️ Ces règles sont vérifiées **côté serveur**, jamais seulement à l'écran. Une case
que l'interface n'affiche pas reste atteignable par l'API — c'est la règle qui a
évité l'incident du triple envoi WhatsApp, et elle vaut dans les deux sens (#480) :
ne pas ouvrir un champ que le serveur ne consomme pas, ne pas laisser le serveur
écrire ce que la règle interdit.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.communaute import OptionSondage, Sondage, VoteSondage
from app.models.core import Batiment, Copropriete, Lot, Utilisateur
from app.routers.sondages.commun import SondageUpdate
from app.routers.sondages.crud import modifier_sondage
from app.seed.patrimoine import poser_arborescence
from app.utils import perimetres as P
from tests.conftest import vider_patrimoine

MODELES_ECRITS = (VoteSondage, OptionSondage, Sondage, Lot, Utilisateur)


@pytest.fixture()
def base():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        vider_patrimoine(session, MODELES_ECRITS)
        copro = Copropriete(nom="Test correction", adresse="1 rue Test")
        session.add(copro)
        session.flush()
        session.add(Batiment(copropriete_id=copro.id, numero="1"))
        session.commit()
        poser_arborescence(session)
        session.commit()
        P.invalider_cache()
        yield session
        vider_patrimoine(session, MODELES_ECRITS)
    P.invalider_cache()


def _user(session: Session, email: str, roles: str = "conseil_syndical") -> Utilisateur:
    u = Utilisateur(
        nom="N", prenom=email.split("@")[0], email=email, roles_json=roles,
        actif=True, decision_compte_le=datetime.utcnow(),
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _sondage(session: Session, auteur: Utilisateur, **kw) -> Sondage:
    kw.setdefault("question", "Question d'origine")
    s = Sondage(auteur_id=auteur.id, **kw)
    session.add(s)
    session.commit()
    session.refresh(s)
    for i, libelle in enumerate(("Oui", "Non")):
        session.add(OptionSondage(sondage_id=s.id, libelle=libelle, ordre=i))
    session.commit()
    session.refresh(s)
    return s


def _voter(session: Session, sondage: Sondage, votant: Utilisateur) -> None:
    option = sorted(sondage.options, key=lambda o: o.ordre)[0]
    session.add(
        VoteSondage(sondage_id=sondage.id, option_id=option.id, user_id=votant.id)
    )
    session.commit()


def _patch(session, sondage, user, **champs):
    return modifier_sondage(
        sondage_id=sondage.id, body=SondageUpdate(**champs), session=session, user=user
    )


# ── Ce qui reste corrigeable, même après un vote ─────────────────────────────

def test_la_question_se_corrige_apres_un_vote(base):
    """Le cas d'usage même du ticket : une faute de frappe ne coûte plus les votes."""
    cs = _user(base, "cs@test.fr")
    votant = _user(base, "votant@test.fr", "résident")
    s = _sondage(base, cs)
    _voter(base, s, votant)

    _patch(base, s, cs, question="Question corrigée")

    base.refresh(s)
    assert s.question == "Question corrigée"
    votes = base.exec(SQLModel.metadata.tables["vote_sondage"].select()).all()
    assert len(votes) == 1, "corriger le texte ne doit toucher AUCUN vote"


def test_le_libelle_d_une_option_se_corrige_apres_un_vote(base):
    cs = _user(base, "cs@test.fr")
    votant = _user(base, "votant@test.fr", "résident")
    s = _sondage(base, cs)
    _voter(base, s, votant)
    option = sorted(s.options, key=lambda o: o.ordre)[0]

    _patch(base, s, cs, options=[{"id": option.id, "libelle": "Oui, sans réserve"}])

    base.refresh(option)
    assert option.libelle == "Oui, sans réserve"
    votes = base.exec(SQLModel.metadata.tables["vote_sondage"].select()).all()
    assert len(votes) == 1, "renommer une option ne déplace ni ne supprime un vote"
    assert votes[0].option_id == option.id


# ── La frontière : ce que le serveur REFUSE ──────────────────────────────────

def test_une_option_d_un_autre_sondage_ne_peut_pas_etre_renommee(base):
    """L'`id` doit appartenir à CE sondage — sinon on renomme le choix d'à côté."""
    cs = _user(base, "cs@test.fr")
    mien = _sondage(base, cs)
    autre = _sondage(base, cs, question="Un autre sondage")
    option_voisine = sorted(autre.options, key=lambda o: o.ordre)[0]

    with pytest.raises(HTTPException) as err:
        _patch(base, mien, cs, options=[{"id": option_voisine.id, "libelle": "Piraté"}])
    assert err.value.status_code == 400

    base.refresh(option_voisine)
    assert option_voisine.libelle == "Oui", "l'option voisine doit être intacte"


def test_un_libelle_vide_est_refuse(base):
    """Une option sans texte est un choix qu'on ne peut plus désigner."""
    cs = _user(base, "cs@test.fr")
    s = _sondage(base, cs)
    option = sorted(s.options, key=lambda o: o.ordre)[0]

    with pytest.raises(HTTPException) as err:
        _patch(base, s, cs, options=[{"id": option.id, "libelle": "   "}])
    assert err.value.status_code == 400


def test_la_cloture_ne_peut_pas_etre_avancee_apres_un_vote(base):
    """Raccourcir prive de leur voix ceux qui n'ont pas encore voté."""
    cs = _user(base, "cs@test.fr")
    votant = _user(base, "votant@test.fr", "résident")
    fin = datetime.utcnow() + timedelta(days=10)
    s = _sondage(base, cs, cloture_le=fin)
    _voter(base, s, votant)

    with pytest.raises(HTTPException) as err:
        _patch(base, s, cs, cloture_le=fin - timedelta(days=5))
    assert err.value.status_code == 400
    base.refresh(s)
    assert s.cloture_le == fin, "la date ne doit pas avoir bougé"


def test_poser_une_echeance_sur_un_sondage_sans_fin_est_un_raccourcissement(base):
    """Le cas qu'une comparaison naïve de dates laisserait passer.

    Un sondage sans `cloture_le` n'a pas de fin. Lui en donner une APRÈS des votes
    n'est pas « reculer », c'est introduire une échéance là où il n'y en avait
    aucune — donc raccourcir, quelle que soit la date choisie.
    """
    cs = _user(base, "cs@test.fr")
    votant = _user(base, "votant@test.fr", "résident")
    s = _sondage(base, cs)  # aucune clôture
    _voter(base, s, votant)

    with pytest.raises(HTTPException) as err:
        _patch(base, s, cs, cloture_le=datetime.utcnow() + timedelta(days=365))
    assert err.value.status_code == 400


# ── Avant le premier vote, rien n'engage personne ────────────────────────────

def test_avant_tout_vote_la_cloture_se_deplace_librement(base):
    """Un sondage que personne n'a lu se corrige sans contrainte."""
    cs = _user(base, "cs@test.fr")
    fin = datetime.utcnow() + timedelta(days=10)
    s = _sondage(base, cs, cloture_le=fin)

    _patch(base, s, cs, cloture_le=fin - timedelta(days=9))

    base.refresh(s)
    assert s.cloture_le < fin, "sans vote exprimé, avancer la clôture est permis"


def test_reculer_la_cloture_reste_permis_apres_un_vote(base):
    """Prolonger n'invalide rien — c'est le sens autorisé."""
    cs = _user(base, "cs@test.fr")
    votant = _user(base, "votant@test.fr", "résident")
    fin = datetime.utcnow() + timedelta(days=2)
    s = _sondage(base, cs, cloture_le=fin)
    _voter(base, s, votant)

    _patch(base, s, cs, cloture_le=fin + timedelta(days=7))

    base.refresh(s)
    assert s.cloture_le > fin


def test_retirer_l_echeance_est_permis_apres_un_vote(base):
    """Retirer la fin = prolonger indéfiniment, donc reculer."""
    cs = _user(base, "cs@test.fr")
    votant = _user(base, "votant@test.fr", "résident")
    s = _sondage(base, cs, cloture_le=datetime.utcnow() + timedelta(days=2))
    _voter(base, s, votant)

    _patch(base, s, cs, cloture_le=None)

    base.refresh(s)
    assert s.cloture_le is None


# ── Le schéma lui-même interdit l'ajout et le retrait ────────────────────────

def test_le_schema_rend_l_ajout_d_option_impossible(base):
    """Pas de garde à oublier : une option sans `id` ne passe pas la validation.

    C'est la différence entre une règle *vérifiée* et une règle *structurelle*.
    Un schéma qui accepterait la liste complète des options supprimerait les
    absentes ; un schéma qui accepterait une option sans `id` en créerait une.
    """
    with pytest.raises(Exception):
        SondageUpdate(options=[{"libelle": "Option ajoutée en douce"}])
