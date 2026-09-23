"""Les anciennes adresses d'actualité mènent à l'affaire (#1091, lot 4 ; #1094).

Chaque courriel et chaque message WhatsApp d'une actualité portait
`/actualites#pub-N`, que l'écran résout par `GET /publications/{N}`. Depuis le
23/09/2026, une actualité est une affaire : la 0210 les a recopiées, et
`ticket.promu_depuis_publication_id` garde l'ancien numéro.

Ce que ces tests verrouillent :

1. **410 avec l'affaire** — « ça a existé, voici où c'est parti » ;
2. **l'affaire est cherchée D'ABORD** : la ligne de `publication` subsiste
   (la 0210 ne supprime rien), et sa présence ne doit pas faire croire qu'elle
   se lit encore ici ;
3. **404 pour un numéro jamais attribué** — sinon on annoncerait une affaire
   qui n'existe pas ;
4. **plus rien d'autre** sous `/publications` : le paquet ne doit pas regrossir
   en silence d'une seconde écriture de l'actualité.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app
from app.models.core import Publication, RoleUtilisateur, Ticket, Utilisateur


@pytest.fixture(name="session")
def session_fixture():
    moteur = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    from app.auth.deps import get_current_user

    lecteur = Utilisateur(email="r@test.fr", hashed_password="x", nom="R", prenom="R",
                          roles_json=RoleUtilisateur.résident.value)
    session.add(lecteur)
    session.commit()
    session.refresh(lecteur)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: lecteur
    yield TestClient(app), lecteur
    app.dependency_overrides.clear()


def test_une_publication_migree_rend_410_avec_son_affaire(session: Session, client):
    http, lecteur = client
    pub = Publication(titre="Coupure", contenu="x", auteur_id=lecteur.id)
    session.add(pub)
    session.commit()
    session.refresh(pub)
    affaire = Ticket(numero="TK-A00001", titre="Coupure", description="x", categorie="actualite",
                     statut="publie", auteur_id=lecteur.id, promu_depuis_publication_id=pub.id)
    session.add(affaire)
    session.commit()

    r = http.get(f"/publications/{pub.id}")
    assert r.status_code == 410, r.text
    assert r.json()["detail"]["promu_en_affaire"] == affaire.id


def test_un_numero_jamais_attribue_rend_404(client):
    http, _ = client
    assert http.get("/publications/999999").status_code == 404


def test_il_ne_reste_que_la_redirection():
    #  Le routeur du paquet, et non `app.routes` : cette version de FastAPI
    #  n'aplatit plus les routes incluses (`test_routeurs_montes.py`).
    from app.routers.publications import router

    chemins = sorted((sorted(r.methods), r.path) for r in router.routes)
    assert chemins == [(["GET"], "/publications/{pub_id}")], chemins
