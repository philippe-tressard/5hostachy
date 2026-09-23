"""Les événements deviennent des affaires — la redirection, la conversion, la visite (#1092, lot 5b2).

Arbitrages de l'utilisateur, 23/09/2026 :

1. **Les anciens liens `/calendrier#ev-N` mènent à l'affaire** : `GET /calendrier/{N}`
   répond 410 avec l'affaire née de l'événement (`promu_depuis_evenement_id`),
   404 pour un numéro jamais attribué — et plus rien d'autre sous `/calendrier`.
2. **La conversion selon le suivi** (migration 0212) : ses trois règles pures sont
   éprouvées ici, la migration entière l'ayant été sur une copie de la base réelle.
3. **La prochaine visite d'un contrat** se recalcule quand un Entretien récurrent
   est résolu — la règle du calendrier, qui suit l'affaire.
"""
from __future__ import annotations

import importlib.util
import pathlib
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app
from app.models.core import RoleUtilisateur, Ticket, Utilisateur
from app.models.prestataires import ContratEntretien, Prestataire
from app.utils.prochaine_visite import apres_cloture, date_prochaine_visite

_MIGRATION = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0212_evenements_deviennent_des_affaires.py"


def _migration():
    spec = importlib.util.spec_from_file_location("m0212", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


# ── 1. La redirection ───────────────────────────────────────────────────────

def test_un_evenement_migre_rend_410_avec_son_affaire(session: Session, client):
    http, lecteur = client
    affaire = Ticket(numero="TK-E00007", titre="AG", description="x", categorie="actualite",
                     statut="publie", auteur_id=lecteur.id, promu_depuis_evenement_id=7)
    session.add(affaire)
    session.commit()
    r = http.get("/calendrier/7")
    assert r.status_code == 410
    assert r.json()["detail"]["promu_en_affaire"] == affaire.id


def test_un_numero_jamais_attribue_rend_404(client):
    http, _ = client
    assert http.get("/calendrier/424242").status_code == 404


def test_il_ne_reste_que_la_redirection_sous_calendrier():
    """Le routeur ne doit pas regrossir en silence d'une seconde écriture."""
    #  Le routeur du paquet, et non `app.routes` : cette version de FastAPI
    #  n'aplatit plus les routes incluses (`test_routeurs_montes.py`).
    from app.routers.calendrier import router

    routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
    assert routes == {("/calendrier/{ev_id}", ("GET",))}, routes


# ── 2. La conversion (0212) ─────────────────────────────────────────────────

@pytest.mark.parametrize("type_, colonne, attendu", [
    ("coupure", "syndic", "actualite"),        # une coupure informe, suivie ou non
    ("ag", None, "actualite"),                  # sans colonne : une information datée
    ("maintenance", "termine", "entretien"),
    ("maintenance_recurrente", "fournisseur", "entretien"),
    ("travaux", "syndic", "etude_travaux"),
    ("ag", "ag", "etude_travaux"),
    ("autre", "annule", "etude_travaux"),
])
def test_la_categorie_suit_le_suivi(type_, colonne, attendu):
    assert _migration().categorie_de(type_, colonne) == attendu


def test_le_public_d_une_actualite_issue_du_calendrier():
    m = _migration()
    assert m.public_de("ag", False) == '["copropriétaires"]'
    assert m.public_de("maintenance_recurrente", False) == '["conseil_syndical"]'
    assert m.public_de("autre", True) == '["conseil_syndical"]'
    assert m.public_de("autre", False) is None


def test_la_description_n_est_jamais_vide_et_garde_le_lieu():
    m = _migration()
    assert m.description_de("Coupure d'eau", None, None) == "<p>Coupure d&#x27;eau</p>"
    avec_lieu = m.description_de("Visite", "<p>Annuelle</p>", "Local chaudière")
    assert avec_lieu.startswith("<p>Lieu : Local chaudière</p>") and avec_lieu.endswith("<p>Annuelle</p>")


def test_le_perimetre_texte_devient_une_liste():
    m = _migration()
    assert m.perimetre_de("bat:1, cave") == '["bat:1", "cave"]'
    assert m.perimetre_de(None) == '["résidence"]'


# ── 3. La prochaine visite ──────────────────────────────────────────────────

@pytest.mark.parametrize("unite, nombre, attendu", [
    ("semaines", 2, date(2026, 10, 7)),
    ("mois", 1, date(2026, 10, 23)),
    ("fois_par_an", 4, date(2026, 12, 23)),
    ("ans", 1, date(2027, 9, 23)),
])
def test_la_date_suit_la_frequence_du_contrat(unite, nombre, attendu):
    contrat = ContratEntretien(prestataire_id=1, libelle="x", type_equipement="autre",
                               date_debut=date(2020, 1, 1), frequence_type=unite, frequence_valeur=nombre)
    assert date_prochaine_visite(contrat, date(2026, 9, 23)) == attendu


def test_un_entretien_recurrent_resolu_avance_la_visite_du_contrat(session: Session, client):
    _, lecteur = client
    p = Prestataire(nom="Otis", specialite="ascenseur")
    session.add(p)
    session.commit()
    session.refresh(p)
    contrat = ContratEntretien(copropriete_id=1, prestataire_id=p.id, libelle="Ascenseur", type_equipement="ascenseur",
                               date_debut=date(2020, 1, 1), frequence_type="mois", frequence_valeur=3,
                               actif=True)
    session.add(contrat)
    t = Ticket(numero="TK-1", titre="Otis — Ascenseur (1/4)", description="x", categorie="entretien",
               statut="résolu", auteur_id=lecteur.id, prestataire_id=p.id, frequence_type="mois",
               frequence_valeur=3, debut=datetime(2026, 9, 23, 10, 0))
    session.add(t)
    session.commit()
    apres_cloture(t, session)
    assert contrat.prochaine_visite == date(2026, 12, 23)


def test_une_affaire_non_recurrente_ne_touche_pas_au_contrat(session: Session, client):
    _, lecteur = client
    p = Prestataire(nom="Sicli", specialite="incendie")
    session.add(p)
    session.commit()
    session.refresh(p)
    contrat = ContratEntretien(copropriete_id=1, prestataire_id=p.id, libelle="Extincteurs", type_equipement="autre",
                               date_debut=date(2020, 1, 1), frequence_type="ans", frequence_valeur=1,
                               actif=True)
    session.add(contrat)
    t = Ticket(numero="TK-2", titre="Extincteurs", description="x", categorie="entretien",
               statut="résolu", auteur_id=lecteur.id, prestataire_id=p.id)
    session.add(t)
    session.commit()
    apres_cloture(t, session)
    assert contrat.prochaine_visite is None
