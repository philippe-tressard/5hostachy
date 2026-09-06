# SPDX-FileCopyrightText: 2026 Philippe Tressard
# SPDX-License-Identifier: MIT
"""Corriger une idée après son dépôt (#783) — et l'auteur qui se cachait sa propre idée.

## Pourquoi ce fichier

Demandé le 06/09/2026 : *« sur idée et sondage : il n'est pas possible de
l'éditer (si erreur de saisie) »*. L'idée était la **seule** entité de la
Communauté sans aucun moyen de se corriger : une faute de frappe y était
définitive, ou imposait de supprimer et redéposer — ce qui perd les votes et les
réponses déjà reçus.

⚠️ Le sondage, lui, avait déjà tout : `PATCH /sondages/{id}` existe, avec ses
arbitrages (clôture qui recule sans jamais avancer, libellés d'options
corrigeables mais liste figée). Il lui manquait seulement un écran. Ne pas
réécrire sa règle ici.

## 🔴 Le défaut trouvé en préparant ce ticket

`cible_visible` ne sortait pas l'auteur. Un locataire qui ciblait son idée sur
les copropriétaires **la faisait disparaître pour lui-même** : plus de carte,
donc plus de bouton, donc plus aucun moyen de corriger le ciblage. Un objet qu'on
ne peut plus ni voir ni retirer est perdu, et **rien ne l'aurait signalé** — la
liste rend simplement un élément de moins.

Livré la veille par #782, trouvé au moment d'écrire l'édition : il fallait que
l'auteur puisse atteindre son objet pour que la question se pose.

## Ce que l'édition NE permet pas, et c'est délibéré

`IdeeUpdate` n'expose ni `perimetre_cible` ni `public_cible` — même décision que
`SondageUpdate` : restreindre après coup masquerait l'idée à des gens qui l'ont
déjà votée. Un champ qu'on n'expose pas ne se contourne pas.

Ni le `statut` : il a sa route, réservée au conseil syndical, qui horodate
`statut_change_le` et prévient les votants. Deux chemins vers le même fait, dont
un qui oublierait les deux effets de bord.
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
from app.routers.annonces import AnnonceCreate, create_annonce
from app.routers.idees import IdeeCreate, IdeeUpdate, create_idee, update_idee
from app.utils.visibility import annonce_visible, idee_visible
from tests.purge_test import purger_ligne


def _utilisateur(role: RoleUtilisateur, statut: StatutUtilisateur, prenom: str) -> Utilisateur:
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


def _supprimer(modele: type, ident: int) -> None:
    with Session(engine) as session:
        purger_ligne(session, modele, ident)
        session.commit()


def _sans_perimetre(modele: type, ident: int) -> None:
    """N'éprouver que le public cible — cf. `test_communaute_public_cible`."""
    with Session(engine) as session:
        objet = session.get(modele, ident)
        objet.perimetre_cible = "[]"
        session.add(objet)
        session.commit()


@pytest.fixture()
def locataire() -> Utilisateur:
    u = _utilisateur(RoleUtilisateur.résident, StatutUtilisateur.locataire, "Lou")
    yield u
    _supprimer(Utilisateur, u.id)


@pytest.fixture()
def voisin() -> Utilisateur:
    u = _utilisateur(
        RoleUtilisateur.propriétaire, StatutUtilisateur.copropriétaire_résident, "Valentin"
    )
    yield u
    _supprimer(Utilisateur, u.id)


@pytest.fixture()
def conseiller() -> Utilisateur:
    u = _utilisateur(
        RoleUtilisateur.conseil_syndical, StatutUtilisateur.copropriétaire_résident, "Charlie"
    )
    yield u
    _supprimer(Utilisateur, u.id)


# ── 🔴 L'auteur voit toujours ce qu'il a écrit ────────────────────────────────

def test_l_auteur_voit_son_idee_meme_s_il_l_a_ciblee_ailleurs(locataire):
    """Sans ce court-circuit, l'auteur perd sa propre idée, sans recours."""
    with Session(engine) as session:
        idee = create_idee(
            IdeeCreate(
                titre="Local vélos",
                description="<p>À couvrir.</p>",
                #  L'auteur est LOCATAIRE et vise les copropriétaires : il
                #  s'exclut lui-même du public visé.
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=locataire,
        )
        idee_id = idee.id
    _sans_perimetre(Idee, idee_id)
    try:
        with Session(engine) as session:
            assert idee_visible(session.get(Idee, idee_id), locataire) is True
    finally:
        _supprimer(Idee, idee_id)


def test_l_auteur_voit_son_annonce_meme_s_il_l_a_ciblee_ailleurs(locataire):
    """Même règle, même écriture — `cible_visible` la porte pour les deux."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(
                titre="Perceuse",
                description="<p>Peu servi.</p>",
                public_cible=["copropriétaires"],
            ),
            session=session,
            user=locataire,
        )
    _sans_perimetre(PetiteAnnonce, cree["id"])
    try:
        with Session(engine) as session:
            assert annonce_visible(session.get(PetiteAnnonce, cree["id"]), locataire) is True
    finally:
        _supprimer(PetiteAnnonce, cree["id"])


def test_un_tiers_hors_public_ne_voit_toujours_pas(locataire, voisin):
    """⚠️ Le court-circuit vaut pour l'AUTEUR, pas pour tout le monde.

    Sans ce test, remplacer la condition par `return True` passerait au vert sur
    les deux précédents.
    """
    with Session(engine) as session:
        idee = create_idee(
            IdeeCreate(
                titre="Composteur", description="<p>Espaces verts.</p>",
                public_cible=["locataires"],
            ),
            session=session,
            user=locataire,
        )
        idee_id = idee.id
    _sans_perimetre(Idee, idee_id)
    try:
        with Session(engine) as session:
            assert idee_visible(session.get(Idee, idee_id), voisin) is False
    finally:
        _supprimer(Idee, idee_id)


# ── Corriger une idée ─────────────────────────────────────────────────────────

def _idee_de(auteur: Utilisateur) -> int:
    """Une idée visible de tous — l'axe géographique est neutralisé.

    ⚠️ Sans cela, un tiers reçoit **404** (l'idée lui est invisible, l'arbre des
    périmètres étant illisible sur une base de test non migrée) au lieu du **403**
    que l'autorisation doit rendre. Le test aurait été vert pour la mauvaise
    raison : il aurait constaté un refus sans jamais atteindre `peut_editer`.
    """
    with Session(engine) as session:
        idee = create_idee(
            IdeeCreate(titre="Boîte à livres", description="<p>Dans le hall.</p>"),
            session=session,
            user=auteur,
        )
        idee_id = idee.id
    _sans_perimetre(Idee, idee_id)
    return idee_id


def test_l_auteur_corrige_son_idee(locataire):
    idee_id = _idee_de(locataire)
    try:
        with Session(engine) as session:
            maj = update_idee(
                idee_id,
                IdeeUpdate(titre="Boîte à livres du hall"),
                session=session,
                user=locataire,
            )
            assert maj["titre"] == "Boîte à livres du hall"
            #  La description n'était pas envoyée : elle ne doit pas être effacée.
            assert maj["description"] == "<p>Dans le hall.</p>"
    finally:
        _supprimer(Idee, idee_id)


def test_un_voisin_ne_corrige_pas_l_idee_d_un_autre(locataire, voisin):
    idee_id = _idee_de(locataire)
    try:
        with Session(engine) as session:
            with pytest.raises(HTTPException) as refus:
                update_idee(
                    idee_id, IdeeUpdate(titre="Détourné"), session=session, user=voisin
                )
            assert refus.value.status_code == 403
    finally:
        _supprimer(Idee, idee_id)


def test_le_conseil_syndical_ne_reecrit_pas_une_idee(locataire, conseiller):
    """🔒 `peut_editer` exclut le CS, et c'est une décision, pas un oubli.

    Il décide du STATUT d'une idée (route dédiée) ; il ne réécrit pas la
    proposition de quelqu'un. C'est exactement la règle du sondage — et c'est la
    même fonction, pas une copie.
    """
    idee_id = _idee_de(locataire)
    try:
        with Session(engine) as session:
            with pytest.raises(HTTPException) as refus:
                update_idee(
                    idee_id, IdeeUpdate(titre="Reformulé"), session=session, user=conseiller
                )
            assert refus.value.status_code == 403
    finally:
        _supprimer(Idee, idee_id)


def test_un_titre_vide_est_refuse(locataire):
    """Un champ requis ne se vide pas par une correction partielle."""
    idee_id = _idee_de(locataire)
    try:
        with Session(engine) as session:
            with pytest.raises(HTTPException) as refus:
                update_idee(idee_id, IdeeUpdate(titre="   "), session=session, user=locataire)
            assert refus.value.status_code == 422
    finally:
        _supprimer(Idee, idee_id)


def test_corriger_ne_repousse_pas_l_archivage(locataire):
    """⚠️ `statut_change_le` ne bouge PAS — c'est lui qui date l'archivage.

    Le toucher ferait repousser l'archivage d'un mois à chaque faute de frappe
    corrigée. `PetiteAnnonce` porte déjà cette leçon, et c'est la raison d'être
    d'un champ distinct de `mis_a_jour_le`.
    """
    idee_id = _idee_de(locataire)
    try:
        with Session(engine) as session:
            avant = session.get(Idee, idee_id).statut_change_le
        with Session(engine) as session:
            update_idee(
                idee_id, IdeeUpdate(description="<p>Corrigée.</p>"),
                session=session, user=locataire,
            )
        with Session(engine) as session:
            assert session.get(Idee, idee_id).statut_change_le == avant
    finally:
        _supprimer(Idee, idee_id)


def test_idee_inexistante_rend_404(locataire):
    with Session(engine) as session:
        with pytest.raises(HTTPException) as refus:
            update_idee(
                999_999, IdeeUpdate(titre="Fantôme"), session=session, user=locataire
            )
        assert refus.value.status_code == 404
