"""Promouvoir une actualité en affaire — **sans rien ressaisir** (#1094).

## Le gain, et il est pour l'utilisateur

Aujourd'hui, une actualité qui dérape — « attention, fuite au 3e » — oblige à
rouvrir une affaire et tout retaper. Après ce lot, un bouton la promeut : titre,
description, pièces jointes et périmètre suivent, et l'on ajoute un statut.

## L'arbitrage du 21/09/2026 : la publication DISPARAÎT

Trois voies étaient possibles — convertir, coexister, archiver. La conversion a
été retenue : *un seul objet à la fois, jamais de doublon*. C'est ce que « le
suivi devient une propriété » veut dire à l'écran.

## 🔴 Ce que la conversion coûtait, et ce qui le paie

Une actualité publiée a déjà été **envoyée par courriel**, avec son adresse
`/actualites#pub-42`. La supprimer sans rien laisser ferait de chacun de ces
courriels un lien mort — le dépôt refuse de renommer les identifiants `TK-xxxx`
pour exactement cette raison.

`promu_depuis_publication_id` garde le numéro de la publication disparue, et
c'est ce qui permet à l'ancienne adresse de mener à l'affaire née d'elle. Le
test le plus important de ce fichier est celui-là : **la trace survit à la
conversion.**

## Ce que ce fichier verrouille

1. tout ce qui devait suivre a suivi, et rien n'a été ressaisi ;
2. la publication a bien disparu, ses évolutions avec elle ;
3. la trace est posée, et l'ancienne adresse retrouve l'affaire ;
4. le geste est réservé — il change la nature d'un objet publié.

⚠️ Le contrôle de droit est vérifié **côté serveur**, pas par l'absence du
bouton : ce que l'interface masque n'est qu'un confort (socle 03 §1).
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app
from app.models.core import (
    Publication,
    PublicationEvolution,
    RoleUtilisateur,
    StatutUtilisateur,
    Ticket,
    Utilisateur,
)

TITRE = "Fuite au 3e étage du bâtiment 2"
CONTENU = "<p>De l'eau coule le long de la cage d'escalier depuis ce matin.</p>"
PHOTOS = ["/uploads/abc-fuite.jpg"]
PERIMETRE = ["bat:2"]


@pytest.fixture(name="session")
def session_fixture():
    moteur = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as session:
        yield session


def _utilisateur(session: Session, role: RoleUtilisateur, email: str) -> Utilisateur:
    u = Utilisateur(
        email=email,
        hashed_password="x",
        nom="Test",
        prenom=role.value,
        role=role,
        roles_json=role.value,
        statut=StatutUtilisateur.copropriétaire_résident,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture(name="cs")
def cs_fixture(session: Session) -> Utilisateur:
    return _utilisateur(session, RoleUtilisateur.conseil_syndical, "cs@test.fr")


@pytest.fixture(name="client")
def client_fixture(session: Session, cs: Utilisateur):
    from app.auth.deps import get_current_user, require_cs_or_admin

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[require_cs_or_admin] = lambda: cs
    app.dependency_overrides[get_current_user] = lambda: cs
    yield TestClient(app)
    app.dependency_overrides.clear()


def _publication(session: Session, auteur: Utilisateur, **kw) -> Publication:
    pub = Publication(
        titre=TITRE,
        contenu=CONTENU,
        perimetre="résidence",
        perimetre_cible=json.dumps(PERIMETRE),
        photos_urls=json.dumps(PHOTOS),
        auteur_id=auteur.id,
        confidentiel=kw.pop("confidentiel", False),
        **kw,
    )
    session.add(pub)
    session.commit()
    session.refresh(pub)
    return pub


def test_tout_ce_qui_devait_suivre_a_suivi(session: Session, client: TestClient, cs):
    """🔴 Le cœur du lot : « rien n'est ressaisi »."""
    pub = _publication(session, cs)

    r = client.post(f"/publications/{pub.id}/promouvoir")
    assert r.status_code == 201, r.text
    affaire = r.json()

    assert affaire["titre"] == TITRE
    #  Le CONTENU d'une actualité devient la DESCRIPTION d'une affaire : deux
    #  noms pour la même chose, et c'est ici que la correspondance s'écrit.
    assert affaire["description"] == CONTENU
    assert affaire["photos_urls"] == PHOTOS
    assert affaire["perimetre_cible"] == PERIMETRE
    #  Une affaire naît ouverte : elle n'a pas encore été regardée.
    assert affaire["statut"] == "ouvert"
    #  Et elle a une identité d'affaire, que l'actualité n'avait pas.
    assert affaire["numero"].startswith("TK-")


def test_la_publication_a_DISPARU(session: Session, client: TestClient, cs):
    """L'arbitrage du 21/09 : un seul objet à la fois, jamais de doublon."""
    pub = _publication(session, cs)
    pub_id = pub.id

    client.post(f"/publications/{pub_id}/promouvoir")

    assert session.get(Publication, pub_id) is None


def test_les_evolutions_de_la_publication_partent_avec_elle(
    session: Session, client: TestClient, cs
):
    """⚠️ Sans cela, la promotion laisserait des lignes orphelines : une
    évolution dont la publication n'existe plus n'est lisible par personne, et
    `_activer_cles_etrangeres` du conftest les refuse en test."""
    pub = _publication(session, cs)
    session.add(
        PublicationEvolution(
            publication_id=pub.id, auteur_id=cs.id, type="commentaire", contenu="Vu ce matin."
        )
    )
    session.commit()
    pub_id = pub.id

    client.post(f"/publications/{pub_id}/promouvoir")

    restantes = session.exec(
        select(PublicationEvolution).where(PublicationEvolution.publication_id == pub_id)
    ).all()
    assert restantes == []


def test_la_TRACE_survit_a_la_conversion(session: Session, client: TestClient, cs):
    """🔴 Le test le plus important du fichier.

    L'actualité a déjà été envoyée par courriel, avec son adresse. Sans cette
    trace, chacun de ces courriels devient un lien mort — et c'est précisément
    ce que le chantier refuse pour les identifiants `TK-xxxx`."""
    pub = _publication(session, cs)
    pub_id = pub.id

    r = client.post(f"/publications/{pub_id}/promouvoir")

    affaire = session.get(Ticket, r.json()["id"])
    assert affaire.promu_depuis_publication_id == pub_id


def test_l_ancienne_adresse_retrouve_l_affaire(session: Session, client: TestClient, cs):
    """Le pendant du précédent, vu du lecteur : ce que la trace SERT à faire."""
    pub = _publication(session, cs)
    pub_id = pub.id
    attendu = client.post(f"/publications/{pub_id}/promouvoir").json()["id"]

    r = client.get(f"/publications/{pub_id}")

    #  410 Gone, et non 404 : la ressource a existé et l'on sait où elle est
    #  allée. Un 404 dirait « ça n'a jamais existé », ce qui est faux et ne
    #  laisse nulle part où aller.
    assert r.status_code == 410, r.text
    assert r.json()["detail"]["promu_en_affaire"] == attendu


def test_une_publication_QUI_EXISTE_se_lit(session: Session, client: TestClient, cs):
    """🔴 Le cas nominal, qu'aucun test ne couvrait (#1167, 23/09/2026).

    Seuls le 410 et le 404 étaient éprouvés. La lecture d'une actualité qui
    existe appelait `publication_visible` avec trois arguments pour deux :
    `TypeError`, donc 500 — sur l'appel que fait chaque lien `#pub-N` d'un
    courriel ou d'un message WhatsApp.
    """
    pub = _publication(session, cs)
    r = client.get(f"/publications/{pub.id}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == pub.id


def test_une_publication_INCONNUE_reste_un_404(session: Session, client: TestClient, cs):
    """⚠️ La nuance qui donne son sens au 410 : sans ce test, rendre 410 pour
    tout identifiant absent passerait — et l'on annoncerait une affaire qui
    n'existe pas."""
    assert client.get("/publications/999999").status_code == 404


def test_un_RESIDENT_ne_promeut_pas(session: Session, client: TestClient, cs):
    """La promotion change la nature d'un objet déjà publié et lui donne un
    statut de suivi : c'est un geste de commandement, réservé au conseil
    syndical et à l'administration (même règle que les champs du même nom dans
    la création d'une affaire).

    ⚠️ Vérifié côté SERVEUR : ce que l'interface masque n'est qu'un confort."""
    from app.auth.deps import require_cs_or_admin

    pub = _publication(session, cs)
    resident = _utilisateur(session, RoleUtilisateur.propriétaire, "resident@test.fr")

    def _refuser():
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Réservé au conseil syndical")

    app.dependency_overrides[require_cs_or_admin] = _refuser
    try:
        r = client.post(f"/publications/{pub.id}/promouvoir")
    finally:
        app.dependency_overrides[require_cs_or_admin] = lambda: cs

    assert r.status_code == 403
    #  Et rien n'a bougé : un refus ne convertit pas à moitié.
    assert session.get(Publication, pub.id) is not None
    assert resident.id is not None


def test_promouvoir_DEUX_fois_est_refuse(session: Session, client: TestClient, cs):
    """La publication n'existe plus : le second appel doit dire quoi, plutôt que
    de créer une seconde affaire depuis rien."""
    pub = _publication(session, cs)
    pub_id = pub.id
    client.post(f"/publications/{pub_id}/promouvoir")

    r = client.post(f"/publications/{pub_id}/promouvoir")

    assert r.status_code in (404, 410)
    affaires = session.exec(
        select(Ticket).where(Ticket.promu_depuis_publication_id == pub_id)
    ).all()
    assert len(affaires) == 1
