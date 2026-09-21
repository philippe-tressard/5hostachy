"""Les **trois** objets « Saisi pour » exposent leur propriétaire — pas seulement le ticket.

## Le défaut (21/09/2026, #1104, signalé à l'écran capture à l'appui)

La carte de TK-417640 affichait « Philippe TRESSARD », celui qui avait tapé, pour
une affaire saisie **pour** quelqu'un d'autre. Le même composant employait
pourtant le bon nom dans la case « Envoyer une copie à … » : un écran, deux
noms, et celui qu'on lit était le mauvais.

## 🔴 Pourquoi un test de STRUCTURE et pas seulement de valeur

Corriger l'écran ne suffisait pas : `proprietaire_nom` n'était déclaré que dans
`TicketRead`. L'actualité et l'événement n'avaient donc **aucune donnée** à
afficher d'autre que leur rédacteur — le défaut était hors de portée du front.

Et il l'était pour une raison qui se répétera : les trois routeurs composaient
le même couple de noms de deux façons différentes. Le ticket appelait
`proprietaire()` puis en dérivait l'affichage ; les deux autres appelaient une
fonction qui refaisait le même appel. Trois écritures d'une question, c'est
trois occasions d'y répondre différemment — et deux l'ont fait.

Ce test verrouille donc les deux bouts :

1. le champ est déclaré **une fois**, dans la classe dont les trois héritent ;
2. les trois routeurs le posent par `noms_derives`, et aucun ne recompose la
   règle chez lui.

⚠️ Un test de valeur seul serait passé au vert le jour où un quatrième objet
porterait le mixin sans que personne ne pense à lui.
"""
from __future__ import annotations

import pathlib

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import Utilisateur
from app.schemas import TicketRead
from app.schemas_evenement import EvenementRead
from app.schemas_publications import PublicationRead
from app.utils.saisi_pour import SaisiPourSortie, noms_derives

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Les trois lectures qui doivent porter le nom du propriétaire, et le routeur
#: qui le pose. Une quatrième entité porteuse devra s'ajouter ici — c'est le
#: seul endroit où la liste s'écrit.
LECTURES = [
    (TicketRead, "routers/tickets/commun.py"),
    (PublicationRead, "routers/publications/commun.py"),
    (EvenementRead, "routers/calendrier.py"),
]


class _Objet:
    """Un porteur des seuls champs que la règle regarde — pas le modèle.

    Volontairement nu : il montre exactement de quoi `noms_derives` dépend, et
    il échouerait si elle se mettait à lire autre chose.
    """

    def __init__(self, auteur_id=None, sp_user=None, sp_nom=None, sp_email=None):
        self.auteur_id = auteur_id
        self.saisi_pour_user_id = sp_user
        self.saisi_pour_nom = sp_nom
        self.saisi_pour_email = sp_email


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        s.add(Utilisateur(id=1, prenom="Alice", nom="Martin", email="alice@x.fr",
                          mot_de_passe_hash="x", role="conseil_syndical"))
        s.add(Utilisateur(id=2, prenom="Bruno", nom="Dupont", email="bruno@x.fr",
                          mot_de_passe_hash="x", role="propriétaire"))
        s.commit()
        yield s


@pytest.mark.parametrize("lecture,_routeur", LECTURES, ids=lambda v: getattr(v, "__name__", v))
def test_les_trois_lectures_portent_le_proprietaire(lecture, _routeur):
    """🔴 Le défaut #1104 côté serveur : seul `TicketRead` le déclarait."""
    assert "proprietaire_nom" in lecture.model_fields, (
        f"{lecture.__name__} n'expose pas `proprietaire_nom` : l'écran ne peut alors "
        "afficher que le rédacteur, quel que soit le « Saisi pour »."
    )


def test_le_champ_est_declare_UNE_fois_dans_la_classe_de_base():
    """⚠️ Trois déclarations séparées divergeraient — c'est ce qui vient
    d'arriver, avec une seule des trois écrite."""
    assert "proprietaire_nom" in SaisiPourSortie.model_fields, (
        "`proprietaire_nom` doit vivre dans `SaisiPourSortie`, dont les trois "
        "lectures héritent déjà — pas recopié dans chacune."
    )
    for lecture, _ in LECTURES:
        propre = {n for n, c in lecture.__annotations__.items()} if hasattr(lecture, "__annotations__") else set()
        assert "proprietaire_nom" not in propre, (
            f"{lecture.__name__} REDÉCLARE `proprietaire_nom` : une redéclaration "
            "peut diverger du parent sans que rien ne le dise."
        )


@pytest.mark.parametrize("_lecture,routeur", LECTURES, ids=lambda v: getattr(v, "__name__", v))
def test_chaque_routeur_pose_le_nom_par_la_fonction_partagee(_lecture, routeur):
    """🔴 Le garde-fou qui compte : un routeur qui recompose la règle chez lui
    passerait les tests de valeur tout en divergeant au premier cas limite."""
    source = (RACINE / routeur).read_text(encoding="utf-8")
    assert "noms_derives" in source, (
        f"{routeur} doit poser les deux noms dérivés par `utils.saisi_pour.noms_derives` "
        "— la règle ne se réécrit pas chez un routeur."
    )
    assert "proprietaire(session," not in source, (
        f"{routeur} recompose le propriétaire à la main : c'est l'écriture que "
        "`noms_derives` remplace, et celle qui a produit #1104."
    )


def test_sans_saisi_pour_les_deux_noms_divergent(session):
    """La nuance qui porte tout l'usage : le propriétaire retombe sur l'auteur,
    l'affichage reste VIDE — sinon chaque entrée porterait « Saisi pour … », y
    compris celles que leur auteur a écrites pour lui-même."""
    proprietaire_nom, affichage = noms_derives(session, _Objet(auteur_id=1))
    assert proprietaire_nom == "Alice MARTIN"
    assert affichage is None


def test_avec_un_resident_inscrit_les_deux_noms_coincident(session):
    """Alice (CS) saisit pour Bruno : c'est Bruno que la carte nomme."""
    proprietaire_nom, affichage = noms_derives(session, _Objet(auteur_id=1, sp_user=2))
    assert proprietaire_nom == "Bruno DUPONT"
    assert affichage == "Bruno DUPONT"


def test_avec_une_personne_exterieure_aussi(session):
    """Le second cas : personne d'inscrit, seulement un nom saisi. Il prime de
    la même façon, et l'absence d'adresse n'y change rien."""
    proprietaire_nom, affichage = noms_derives(
        session, _Objet(auteur_id=1, sp_nom="Paul EXTERNE")
    )
    assert proprietaire_nom == "Paul EXTERNE"
    assert affichage == "Paul EXTERNE"


def test_un_saisi_pour_introuvable_retombe_sur_l_auteur(session):
    """⚠️ Le compte a été supprimé depuis la saisie. Le propriétaire reprend
    l'auteur — mais l'affichage, lui, reste renseigné : les champs sont TOUJOURS
    là, et l'écran doit continuer de dire que cette entrée a été saisie pour
    quelqu'un, même si l'on ne sait plus pour qui."""
    proprietaire_nom, affichage = noms_derives(session, _Objet(auteur_id=1, sp_user=999))
    assert proprietaire_nom == "Alice MARTIN"
    assert affichage == "Alice MARTIN"
