"""Corriger une entrée de fil : les deux fils disent la MÊME chose (#779).

Pendant de `test_evolutions_suppression.py`, pour l'autre geste. Effacer était
déjà factorisé (#512) ; **corriger** ne l'était pas : la garde du
`PATCH …/evolutions/{id}` était écrite deux fois, publications et tickets, y
compris le tuple `("commentaire", "etat")` recopié à la main **à deux pas du
module qui le porte déjà**. Trois copies d'une même liste, dont deux qui
s'ignoraient.

⚠️ Une garde d'autorisation recopiée est une garde qu'on durcira d'un côté
seulement — et c'est le côté non durci qui décide de ce qui passe.

## Ce qui est éprouvé ici

Le **comportement** de la garde partagée, sur les deux modèles : l'ordre des
trois refus, et le fait qu'une entrée tracée automatiquement ne se corrige pas.
Que les deux routes l'appellent bien est vérifié par analyse statique, comme le
fait le fichier jumeau pour la suppression : une dépendance relâchée ne se voit
pas dans une réponse HTTP nominale.
"""
from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app.models.core import TicketEvolution, Utilisateur
from app.utils.evolutions import TYPES_EFFACABLES, evolution_modifiable

RACINE = pathlib.Path(__file__).resolve().parents[1] / "app"

#: (modèle, colonne du parent, fichier de la route)
FILS = [
    (TicketEvolution, "ticket_id", "routers/tickets/evolutions.py"),
]
#  Le fil des publications est parti avec elles le 23/09/2026 (#1091) : la Suite
#  d'une actualité est celle d'une affaire.
IDS = ["tickets"]


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


def _auteur(session, email="auteur@exemple.fr"):
    u = Utilisateur(email=email, hashed_password="x", prenom="A", nom="B")
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _entree(session, modele, champ_parent, parent_id, auteur, type_="commentaire"):
    evol = modele()
    setattr(evol, champ_parent, parent_id)
    evol.type = type_
    evol.contenu = "texte"
    evol.auteur_id = auteur.id
    session.add(evol)
    session.commit()
    session.refresh(evol)
    return evol


@pytest.mark.parametrize("modele,champ,_", FILS, ids=IDS)
def test_l_auteur_peut_corriger_son_entree(session, modele, champ, _):
    auteur = _auteur(session)
    evol = _entree(session, modele, champ, 1, auteur)
    assert evolution_modifiable(
        session, modele, evol.id, champ_parent=champ, parent_id=1, user=auteur
    ).id == evol.id


@pytest.mark.parametrize("modele,champ,_", FILS, ids=IDS)
def test_une_entree_d_un_AUTRE_objet_est_introuvable(session, modele, champ, _):
    """🔒 404, et l'appartenance se vérifie AVANT tout le reste.

    Sans elle, un identifiant d'entrée valide permettrait de corriger l'entrée
    d'un autre objet que celui dont on a l'adresse — et le contrôle d'accès de
    l'URL ne servirait à rien. C'est le même raisonnement que la suppression.
    """
    auteur = _auteur(session)
    evol = _entree(session, modele, champ, 1, auteur)
    with pytest.raises(HTTPException) as erreur:
        evolution_modifiable(
            session, modele, evol.id, champ_parent=champ, parent_id=2, user=auteur
        )
    assert erreur.value.status_code == 404


@pytest.mark.parametrize("modele,champ,_", FILS, ids=IDS)
def test_une_entree_tracee_automatiquement_ne_se_corrige_pas(session, modele, champ, _):
    """Une « Correction : … » posée par le serveur ne décrit le geste de personne."""
    auteur = _auteur(session)
    evol = _entree(session, modele, champ, 1, auteur, type_="correction")
    with pytest.raises(HTTPException) as erreur:
        evolution_modifiable(
            session, modele, evol.id, champ_parent=champ, parent_id=1, user=auteur
        )
    assert erreur.value.status_code == 422


@pytest.mark.parametrize("modele,champ,_", FILS, ids=IDS)
def test_le_type_passe_AVANT_le_droit(session, modele, champ, _):
    """Un tiers sur une entrée non corrigeable obtient 422, pas 403.

    ⚠️ L'ordre des refus n'est pas décoratif : inversé, il dirait « accès
    refusé » là où la vraie raison est que l'objet ne se corrige pas — et
    laisserait croire qu'un droit supplémentaire y donnerait accès.
    """
    auteur = _auteur(session)
    tiers = _auteur(session, "tiers@exemple.fr")
    evol = _entree(session, modele, champ, 1, auteur, type_="correction")
    with pytest.raises(HTTPException) as erreur:
        evolution_modifiable(
            session, modele, evol.id, champ_parent=champ, parent_id=1, user=tiers
        )
    assert erreur.value.status_code == 422


@pytest.mark.parametrize("modele,champ,fichier", FILS, ids=IDS)
def test_chaque_route_delegue_a_la_garde_partagee(modele, champ, fichier):
    """Par ANALYSE STATIQUE : une garde recopiée ne se voit pas à l'exécution.

    Un test fonctionnel qui appelle la route en auteur passe tout aussi bien si
    la route a gardé sa propre copie — c'est la leçon du fichier jumeau.
    """
    source = (RACINE / fichier).read_text(encoding="utf-8")
    arbre = ast.parse(source)
    patch = next(
        n for n in ast.walk(arbre)
        if isinstance(n, ast.FunctionDef) and n.name == "update_evolution"
    )
    appels = {
        n.func.id for n in ast.walk(patch)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "evolution_modifiable" in appels, (
        f"{fichier} : le PATCH ne passe pas par la garde partagée — "
        "la copie reviendra, et elle divergera"
    )
    #  🔴 Et le tuple ne se réécrit pas sur place : c'est ce qui était fait.
    assert '("commentaire", "etat")' not in source, (
        f"{fichier} : la liste des types est recopiée — elle vit dans "
        "`app/utils/evolutions.TYPES_EFFACABLES`"
    )


def test_cas_zero_la_liste_des_types_n_est_pas_vide():
    """Une liste vidée ferait passer « rien n'est corrigeable » pour une règle."""
    assert TYPES_EFFACABLES, "TYPES_EFFACABLES est vide — le relevé est cassé"
