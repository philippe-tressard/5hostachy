"""La 0210 fait des publications des affaires « Actualité » — et le défait (#1091).

Exécutée pour de vrai, par le contexte d'Alembic, sur une base en mémoire peuplée
de publications de chaque sorte : ouverte, urgente, réservée au conseil, réservée
au périmètre, annulée, avec évolutions, document, affiche et carte masquée.
C'est la migration de données la plus lourde du chantier : elle se prouve avant
de toucher une base en service.
"""
from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.annonce_hall import AnnonceHall
from app.models.communaute import FluxMasque
from app.models.core import Publication, PublicationEvolution, Ticket, TicketEvolution, Utilisateur
from app.models.documents import Document

_MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0210_actualites_deviennent_des_affaires.py"


def _module():
    spec = importlib.util.spec_from_file_location("mig0210", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jouer(moteur, sens: str) -> None:
    with moteur.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(_module(), sens)()


@pytest.fixture()
def base():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        auteur = Utilisateur(email=f"a-{uuid.uuid4().hex[:6]}@x.fr", mot_de_passe_hash="x", prenom="A", nom="B")
        s.add(auteur)
        s.commit()
        s.refresh(auteur)
        quand = datetime(2026, 9, 1, 10, 0)

        def pub(**kw):
            p = Publication(titre=kw.pop("titre"), contenu="Texte", auteur_id=auteur.id, cree_le=quand, **kw)
            s.add(p)
            s.commit()
            s.refresh(p)
            return p

        ouverte = pub(titre="Ouverte", public_cible='["résidents"]', epingle=True)
        urgente = pub(titre="Urgente", urgente=True, public_cible='["copropriétaires"]')
        reservee = pub(titre="Réservée", brouillon=True)
        perimetre = pub(titre="Périmètre", confidentiel=True, perimetre_cible='["bat:1"]')
        annulee = pub(titre="Annulée", statut="annule")
        s.add(PublicationEvolution(publication_id=ouverte.id, type="etat", ancien_statut="publie",
                                   nouveau_statut="resolu", auteur_id=auteur.id, cree_le=quand))
        s.add(Document(titre="Plan", fichier_nom="plan.pdf", publication_id=ouverte.id, fichier_chemin="/tmp/x.pdf", publie_par_id=auteur.id))
        s.add(AnnonceHall(titre="Affiche", message="m", publication_id=ouverte.id, auteur_id=auteur.id))
        s.add(FluxMasque(item_id=f"pub_{urgente.id}", masque_par_id=auteur.id))
        s.commit()
        ids = {p.titre: p.id for p in (ouverte, urgente, reservee, perimetre, annulee)}
    return moteur, ids


def _affaire(s, pid) -> Ticket:
    return s.exec(select(Ticket).where(Ticket.promu_depuis_publication_id == pid)).one()


def test_chaque_publication_devient_une_affaire_actualite(base):
    moteur, ids = base
    _jouer(moteur, "upgrade")
    with Session(moteur) as s:
        o = _affaire(s, ids["Ouverte"])
        assert (o.categorie, o.statut, o.description) == ("actualite", "publie", "Texte")
        assert o.public_cible is None, "« Tous les résidents » devient « tout le monde »"
        assert o.epingle is True
        assert o.numero == f"TK-A{ids['Ouverte']:05d}"
        assert _affaire(s, ids["Urgente"]).priorite == "haute"
        assert _affaire(s, ids["Urgente"]).public_cible == '["copropriétaires"]'
        assert _affaire(s, ids["Réservée"]).public_cible == '["conseil_syndical"]', "#1096"
        assert _affaire(s, ids["Périmètre"]).reserve_perimetre is True
        assert _affaire(s, ids["Annulée"]).archive_manuel is True


def test_ce_qui_s_y_rattache_suit(base):
    moteur, ids = base
    _jouer(moteur, "upgrade")
    with Session(moteur) as s:
        o = _affaire(s, ids["Ouverte"])
        evol = s.exec(select(TicketEvolution).where(TicketEvolution.ticket_id == o.id)).one()
        assert (evol.ancien_statut, evol.nouveau_statut) == ("publie", "résolu")
        doc = s.exec(select(Document)).one()
        assert (doc.ticket_id, doc.publication_id) == (o.id, None)
        assert s.exec(select(AnnonceHall)).one().ticket_id == o.id
        u = _affaire(s, ids["Urgente"])
        assert s.exec(select(FluxMasque)).one().item_id == f"tk_{u.id}"
        #  Rien n'est supprimé : les publications restent, lues par rien.
        assert len(s.exec(select(Publication)).all()) == 5


def test_la_rejouer_ne_duplique_rien(base):
    moteur, _ = base
    _jouer(moteur, "upgrade")
    _jouer(moteur, "upgrade")
    with Session(moteur) as s:
        assert len(s.exec(select(Ticket)).all()) == 5
        assert len(s.exec(select(TicketEvolution)).all()) == 1


def test_le_retour_arriere_rend_l_etat_de_depart(base):
    moteur, ids = base
    _jouer(moteur, "upgrade")
    _jouer(moteur, "downgrade")
    with Session(moteur) as s:
        assert s.exec(select(Ticket)).all() == []
        assert s.exec(select(TicketEvolution)).all() == []
        doc = s.exec(select(Document)).one()
        assert (doc.publication_id, doc.ticket_id) == (ids["Ouverte"], None)
        assert s.exec(select(FluxMasque)).one().item_id == f"pub_{ids['Urgente']}"
        assert s.exec(select(AnnonceHall)).one().ticket_id is None
