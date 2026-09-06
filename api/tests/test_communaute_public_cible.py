# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: MIT
"""Le public cible d'une annonce et d'une idée protège **tous** les chemins (#782).

## Ce que ce test verrouille, et pourquoi ce n'est pas la liste

Ouvrir le ciblage à une entité, c'est ouvrir autant de portes qu'elle a
d'endpoints. Filtrer la liste est la partie visible — et la moins utile seule :
une carte absente de l'écran reste atteignable en appelant l'API directement.

Les chemins qui comptent ici :

| Chemin | Ce qu'un exclu pourrait faire sans contrôle |
|---|---|
| liste | voir l'objet |
| lire les réponses | lire ce que les voisins en disent |
| écrire une réponse | s'inviter dans la conversation |
| **voter** (idée) | **peser sur un résultat qui ne le regarde pas** |

Les trois routes de réponses vérifiaient l'**existence** de la cible, jamais sa
visibilité : inoffensif tant qu'annonces et idées s'adressaient à tous, exploitable
dès l'ouverture du public cible. Corrigé dans la fabrique, donc pour les deux
rubriques à la fois.

## 🔒 404 et non 403

Répondre « interdit » confirmerait l'existence de l'objet à qui n'a pas le droit
de le voir : sur une petite annonce, cela révélerait qu'un voisin vend quelque
chose sans dire quoi.

## ⚠️ Le cas zéro est le plus important de ce fichier

**Absence de public cible = visible de tous**, jamais « visible de personne ».
C'est ce que portent toutes les annonces et idées déposées avant la migration
0176. L'inverse les aurait fait disparaître d'un coup, sans message ni ligne de
journal — la panne la plus difficile à diagnostiquer, parce que rien ne casse.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import (
    Idee,
    PetiteAnnonce,
    RoleUtilisateur,
    StatutUtilisateur,
    Utilisateur,
)
from app.routers.annonces import AnnonceCreate, create_annonce, list_annonces
from app.routers.idees import IdeeCreate, create_idee, list_idees, voter
from app.utils.visibility import annonce_visible, idee_visible
from tests.purge_test import purger_ligne


def _utilisateur(
    role: RoleUtilisateur, statut: StatutUtilisateur | None, prenom: str
) -> Utilisateur:
    """⚠️ Le public cible se décide sur le STATUT, le périmètre sur le rôle.

    Les confondre est l'erreur naturelle : « locataire » est un statut et non un
    rôle, et `RoleUtilisateur` n'en a pas. C'est `public_cible_visible` qui lit
    `user.statut` — un test qui n'aurait posé que le rôle aurait vu passer tout
    le monde et conclu que le ciblage marchait.
    """
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        u = Utilisateur(
            email=f"{prenom.lower()}-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x",
            prenom=prenom,
            nom="Aulnay",
            role=role,
            statut=statut,
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        return u


def _sans_perimetre(modele: type, ident: int) -> None:
    """Neutralise l'axe GÉOGRAPHIQUE pour n'éprouver que le public cible.

    ⚠️ Ce n'est pas une commodité : `perimetre_visible` lit l'arbre des périmètres
    en base, et le refuse quand il est illisible — « un contrôle qui ne peut pas
    s'exécuter renvoie INCONNU, jamais OK » (`standards/04`). Sur une base de test
    dont la table `perimetre` n'est pas migrée, TOUT est donc invisible, et un
    test du public cible passerait au vert pour la mauvaise raison : il verrait
    l'objet caché sans que sa propre règle y soit pour quoi que ce soit.

    Un périmètre vide court-circuite cette lecture. Les deux axes restent testés
    séparément — celui-ci l'est déjà par `test_annonce_perimetre.py`.
    """
    with Session(engine) as session:
        objet = session.get(modele, ident)
        objet.perimetre_cible = "[]"
        session.add(objet)
        session.commit()


def _supprimer(modele: type, ident: int) -> None:
    with Session(engine) as session:
        purger_ligne(session, modele, ident)
        session.commit()


@pytest.fixture()
def locataire() -> Utilisateur:
    u = _utilisateur(RoleUtilisateur.résident, StatutUtilisateur.locataire, "Lou")
    yield u
    _supprimer(Utilisateur, u.id)


@pytest.fixture()
def coproprietaire() -> Utilisateur:
    u = _utilisateur(
        RoleUtilisateur.propriétaire, StatutUtilisateur.copropriétaire_résident, "Camille"
    )
    yield u
    _supprimer(Utilisateur, u.id)


@pytest.fixture()
def conseiller() -> Utilisateur:
    u = _utilisateur(RoleUtilisateur.conseil_syndical, StatutUtilisateur.copropriétaire_résident, "Charlie")
    yield u
    _supprimer(Utilisateur, u.id)


# ── Petite annonce ────────────────────────────────────────────────────────────

def test_annonce_ciblee_invisible_hors_public(locataire, coproprietaire):
    """Une annonce réservée aux copropriétaires n'apparaît pas au locataire."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(
                titre="Cave à vendre",
                description="<p>10 m².</p>",
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=coproprietaire,
        )
    _sans_perimetre(PetiteAnnonce, cree["id"])
    try:
        with Session(engine) as session:
            annonce = session.get(PetiteAnnonce, cree["id"])
            assert annonce_visible(annonce, coproprietaire) is True
            assert annonce_visible(annonce, locataire) is False
            titres = [a["titre"] for a in list_annonces(session=session, user=locataire)]
            assert "Cave à vendre" not in titres
    finally:
        _supprimer(PetiteAnnonce, cree["id"])


def test_annonce_sans_public_cible_reste_visible_de_tous(locataire, coproprietaire):
    """🔴 LE CAS ZÉRO : rien de précisé = tout le monde, jamais personne."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(titre="Table basse", description="<p>Chêne.</p>"),
            session=session,
            user=coproprietaire,
        )
    _sans_perimetre(PetiteAnnonce, cree["id"])
    try:
        with Session(engine) as session:
            annonce = session.get(PetiteAnnonce, cree["id"])
            #  `None` en base, et non `"[]"` : c'est ce que portent les annonces
            #  déposées avant la migration 0176.
            assert annonce.public_cible is None
            assert annonce_visible(annonce, locataire) is True
    finally:
        _supprimer(PetiteAnnonce, cree["id"])


def test_annonce_ciblee_reste_visible_du_conseil(locataire, coproprietaire, conseiller):
    """Le CS voit tout — c'est ce qui lui laisse de quoi corriger un ciblage fautif."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(
                titre="Poussette",
                description="<p>Bon état.</p>",
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=coproprietaire,
        )
    _sans_perimetre(PetiteAnnonce, cree["id"])
    try:
        with Session(engine) as session:
            annonce = session.get(PetiteAnnonce, cree["id"])
            assert annonce_visible(annonce, conseiller) is True
            assert annonce_visible(annonce, locataire) is False
    finally:
        _supprimer(PetiteAnnonce, cree["id"])


# ── Idée ──────────────────────────────────────────────────────────────────────

def test_idee_ciblee_invisible_hors_public(locataire, coproprietaire):
    with Session(engine) as session:
        idee = create_idee(
            IdeeCreate(
                titre="Refaire le local vélos",
                description="<p>Il pleut dedans.</p>",
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=coproprietaire,
        )
        idee_id = idee.id
    _sans_perimetre(Idee, idee_id)
    try:
        with Session(engine) as session:
            objet = session.get(Idee, idee_id)
            assert idee_visible(objet, coproprietaire) is True
            assert idee_visible(objet, locataire) is False
            titres = [i["titre"] for i in list_idees(session=session, user=locataire)]
            assert "Refaire le local vélos" not in titres
    finally:
        _supprimer(Idee, idee_id)


def test_voter_sur_une_idee_non_visible_est_refuse(locataire, coproprietaire):
    """🔒 Le chemin qui compte : voter pèse sur un résultat.

    La liste ne montrait déjà plus l'idée ; sans ce contrôle, l'endpoint restait
    appelable directement — et un exclu votait.
    """
    with Session(engine) as session:
        idee = create_idee(
            IdeeCreate(
                titre="Composteur collectif",
                description="<p>Dans les espaces verts.</p>",
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=coproprietaire,
        )
        idee_id = idee.id
    _sans_perimetre(Idee, idee_id)
    try:
        with Session(engine) as session:
            with pytest.raises(HTTPException) as refus:
                voter(idee_id, session=session, user=locataire)
            #  404 et non 403 : ne pas confirmer l'existence de l'idée.
            assert refus.value.status_code == 404
    finally:
        _supprimer(Idee, idee_id)


def test_idee_sans_public_cible_reste_votable(locataire, coproprietaire):
    """Le cas zéro, sur le chemin d'écriture : une idée non ciblée se vote."""
    with Session(engine) as session:
        idee = create_idee(
            IdeeCreate(titre="Boîte à livres", description="<p>Dans le hall.</p>"),
            session=session,
            user=coproprietaire,
        )
        idee_id = idee.id
    _sans_perimetre(Idee, idee_id)
    try:
        with Session(engine) as session:
            resultat = voter(idee_id, session=session, user=locataire)
            assert resultat is not None
    finally:
        _supprimer(Idee, idee_id)
