"""Le périmètre d'une petite annonce fait l'aller-retour **sans se perdre**.

## Pourquoi ce garde-fou (18/08/2026, migration 0151)

Le périmètre voyage sous **deux formes** : une liste de codes côté API
(`["bat:1", "parking"]`), une chaîne JSON côté colonne. La conversion se fait à
la frontière, dans `routers/annonces.py`, et elle a un mode d'échec silencieux :

    setattr(annonce, "perimetre_cible", ["bat:1"])   # une LISTE sur une colonne TEXTE

SQLite ne refuse pas — il enregistre la *repr* Python de la liste,
`"['bat:1']"`, avec des apostrophes simples. `json.loads` ne la relit pas, la
lecture retombe sur le défaut, et **l'annonce perd son périmètre à la première
correction**. Rien ne lève, rien ne se voit à l'enregistrement : l'écran affiche
« résidence » comme si l'utilisateur l'avait choisi.

⚠️ C'est exactement le genre de défaut que le mode édition **crée** : au dépôt,
`create_annonce` sérialise explicitement ; c'est la boucle `setattr` du `PATCH`
qui ne le faisait pas. Un champ correct à la création et cassé à la correction
n'apparaît qu'au deuxième geste — donc jamais pendant qu'on développe le premier.

Le test vérifie **le fait** : il relit la colonne brute en base après l'appel, au
lieu de croire le corps de la réponse (`standards/04` §14 — observer la chose,
pas son enregistrement). Une réponse fabriquée à partir de l'objet en mémoire
serait juste alors que la base serait fausse.
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import PetiteAnnonce, RoleUtilisateur, Utilisateur
from app.routers.annonces import AnnonceCreate, AnnonceUpdate, create_annonce, update_annonce


@pytest.fixture()
def resident() -> Utilisateur:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        u = Utilisateur(
            email=f"resident-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x",
            prenom="Robin",
            nom="Aulnay",
            role=RoleUtilisateur.résident,
        )
        session.add(u)
        session.commit()
        session.refresh(u)
        yield u
        session.delete(session.get(Utilisateur, u.id))
        session.commit()


def _colonne_brute(annonce_id: int) -> str | None:
    """La valeur telle qu'elle est ÉCRITE, sans passer par l'enrichissement."""
    with Session(engine) as session:
        return session.get(PetiteAnnonce, annonce_id).perimetre_cible


def test_depot_ecrit_du_json_relisible(resident):
    """`POST` : la liste reçue devient du JSON, pas une repr Python."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(
                titre="Vélo d'appartement",
                description="<p>Peu servi.</p>",
                perimetre_cible=["bat:1", "parking"],
            ),
            session=session,
            user=resident,
        )
    try:
        brut = _colonne_brute(cree["id"])
        assert json.loads(brut) == ["bat:1", "parking"]
        assert cree["perimetre_cible"] == ["bat:1", "parking"]
    finally:
        with Session(engine) as session:
            session.delete(session.get(PetiteAnnonce, cree["id"]))
            session.commit()


def test_correction_ecrit_du_json_relisible(resident):
    """`PATCH` : c'est ici que la liste se posait telle quelle sur la colonne."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(titre="Table basse", description="<p>Chêne.</p>"),
            session=session,
            user=resident,
        )
    try:
        with Session(engine) as session:
            maj = update_annonce(
                cree["id"],
                AnnonceUpdate(perimetre_cible=["cave"]),
                session=session,
                user=resident,
            )
        brut = _colonne_brute(cree["id"])
        assert json.loads(brut) == ["cave"], (
            f"périmètre illisible en base : {brut!r} — la liste a été posée sans "
            "être sérialisée, et la prochaine lecture retombera sur le défaut."
        )
        assert maj["perimetre_cible"] == ["cave"]
    finally:
        with Session(engine) as session:
            session.delete(session.get(PetiteAnnonce, cree["id"]))
            session.commit()


def test_correction_sans_perimetre_ne_l_efface_pas(resident):
    """Corriger un titre ne touche pas au périmètre — `exclude_none` le garantit,
    et c'est le genre de garantie qui saute à la première réécriture du `PATCH`."""
    with Session(engine) as session:
        cree = create_annonce(
            AnnonceCreate(
                titre="Poussette",
                description="<p>Bon état.</p>",
                perimetre_cible=["bat:3"],
            ),
            session=session,
            user=resident,
        )
    try:
        with Session(engine) as session:
            update_annonce(
                cree["id"],
                AnnonceUpdate(titre="Poussette double"),
                session=session,
                user=resident,
            )
        assert json.loads(_colonne_brute(cree["id"])) == ["bat:3"]
    finally:
        with Session(engine) as session:
            session.delete(session.get(PetiteAnnonce, cree["id"]))
            session.commit()


def test_annonce_anterieure_a_la_migration_se_lit_comme_residence(resident):
    """Une annonce déposée AVANT 0151 porte `NULL` : elle valait « résidence » de
    fait, elle doit le valoir explicitement — sinon `perimetreLabel` reçoit `null`
    et la carte affiche un badge vide au lieu de n'en afficher aucun."""
    with Session(engine) as session:
        ancienne = PetiteAnnonce(
            titre="Ancienne annonce",
            description="<p>Déposée avant la migration.</p>",
            auteur_id=resident.id,
            perimetre_cible=None,
        )
        session.add(ancienne)
        session.commit()
        session.refresh(ancienne)
        annonce_id = ancienne.id

    try:
        with Session(engine) as session:
            lue = update_annonce(
                annonce_id,
                AnnonceUpdate(titre="Ancienne annonce (corrigée)"),
                session=session,
                user=resident,
            )
        assert lue["perimetre_cible"] == ["résidence"]
    finally:
        with Session(engine) as session:
            session.delete(session.get(PetiteAnnonce, annonce_id))
            session.commit()
