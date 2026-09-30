"""Carnet = Affaires = Kanban — le standard de lecture du 30/09/2026.

Arbitré par l'utilisateur : ce qu'un copropriétaire lit au carnet d'entretien,
il le lit dans les affaires et au kanban, et une affaire qu'il ne lit pas
DISPARAÎT du carnet. Le carnet montrait jusque-là à tout copropriétaire le
titre, le numéro et le lien de toute affaire résolue du bâti — sinistre nommant
un lot, étude réservée au conseil, affaire confidentielle comprises — et la
fiche refusait ensuite de s'ouvrir.

La règle de lecture elle-même (qui lit quoi, par statut) est tenue par
`donnees/lecture_pastille.json` ; ce fichier tient ce qui l'y RELIE :

1. le carnet applique `ticket_visible`, lecteur par lecteur ;
2. une Suite dont l'ÉTAT ouvre une Étude & travaux le dit dans le fil ;
3. une étude ouverte par son état peut sortir (groupe, hall) — fermée, non.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import StatutTicket, StatutUtilisateur, Ticket, Utilisateur
from app.routers.tickets.evolutions import add_evolution
from app.schemas import TicketEvolutionCreate
from app.utils import mes_batiments
from app.utils import perimetres as P
from app.utils.carnet_entretien import construire_carnet
from app.utils.visibility import reservee_au_conseil, ticket_visible
from tests.aides_base import compte
from tests.purge_test import purger_ligne


def _compte(session, roles: str, statut=None, batiment_id=None) -> Utilisateur:
    return compte(
        session,
        prefixe="carnet-lu",
        prenom="Camille",
        nom="Sorel",
        roles_json=roles,
        statut=statut,
        batiment_id=batiment_id,
    )


@pytest.fixture()
def contexte(batiments):
    """Le conseil, et un copropriétaire d'un AUTRE bâtiment que celui des affaires."""
    SQLModel.metadata.create_all(engine)
    mes_batiments.invalider_cache()
    P.invalider_cache()
    with Session(engine) as session:
        cs = _compte(session, "conseil_syndical")
        copro = _compte(
            session,
            "propriétaire",
            StatutUtilisateur.copropriétaire_résident,
            batiment_id=batiments[1],
        )
        mes_batiments.invalider_cache()
        crees: list[Ticket] = []

        def affaire(categorie, statut=StatutTicket.résolu, public=None, confidentiel=False):
            t = Ticket(
                numero=f"T-{uuid.uuid4().hex[:6]}",
                titre=f"Carnet {categorie} {uuid.uuid4().hex[:4]}",
                description="…",
                categorie=categorie,
                auteur_id=cs.id,
                statut=statut,
                ferme_le=datetime(2026, 9, 25, 10, 0),
                perimetre_cible=json.dumps([f"bat:{batiments[0]}"]),
                public_cible=json.dumps(public, ensure_ascii=False) if public else None,
                confidentiel=confidentiel,
            )
            session.add(t)
            session.commit()
            session.refresh(t)
            crees.append(t)
            return t

        yield session, cs, copro, affaire
        for t in crees:
            purger_ligne(session, Ticket, t.id)
        for u in (cs, copro):
            purger_ligne(session, Utilisateur, u.id)
        session.commit()
        mes_batiments.invalider_cache()


def _titres(session, lecteur) -> set[str]:
    return {e["libelle"] for e in construire_carnet(session, lecteur=lecteur)}


def test_le_carnet_d_un_coproprietaire_est_celui_des_affaires(contexte):
    """Ce que le carnet montre, la fiche l'ouvre — et réciproquement."""
    session, cs, copro, affaire = contexte
    lues = [affaire("panne"), affaire("entretien"), affaire("etude_travaux")]
    cachees = [
        affaire("sinistre"),
        affaire("etude_travaux", public=["conseil_syndical"]),
        affaire("panne", confidentiel=True),
    ]
    titres = _titres(session, copro)
    for t in lues:
        assert ticket_visible(t, copro)
        assert t.titre in titres, f"« {t.titre} » : lue dans les affaires, absente du carnet"
    for t in cachees:
        assert not ticket_visible(t, copro)
        assert t.titre not in titres, f"« {t.titre} » : fermée dans les affaires, lue au carnet"
    #  Le conseil, lui, voit tout — le carnet n'a rien perdu.
    assert {t.titre for t in lues + cachees} <= _titres(session, cs)


def test_une_suite_qui_met_l_etude_en_ag_ouvre_le_fil_et_le_dit(contexte):
    session, cs, copro, affaire = contexte
    t = affaire("etude_travaux", statut=StatutTicket.ouvert)
    assert not ticket_visible(t, copro)
    evol = add_evolution(
        t.id,
        TicketEvolutionCreate(type="etat", nouveau_statut="en_ag", contenu="Soumise au vote."),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    session.refresh(t)
    assert ticket_visible(t, copro)
    assert "Lue par défaut" in evol.contenu and "Copropriétaires" in evol.contenu


def test_un_changement_d_etat_qui_ne_change_pas_les_lecteurs_ne_dit_rien(contexte):
    session, cs, _copro, affaire = contexte
    t = affaire("etude_travaux", statut=StatutTicket.ouvert)
    evol = add_evolution(
        t.id,
        TicketEvolutionCreate(type="etat", nouveau_statut="en_cours", contenu="On avance."),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    assert "Lue par défaut" not in (evol.contenu or "")


def test_le_choix_du_conseil_prime_sur_l_etat_et_la_suite_se_tait(contexte):
    session, cs, copro, affaire = contexte
    t = affaire("etude_travaux", statut=StatutTicket.ouvert, public=["conseil_syndical"])
    evol = add_evolution(
        t.id,
        TicketEvolutionCreate(type="etat", nouveau_statut="résolu", contenu="Close."),
        BackgroundTasks(),
        session=session,
        user=cs,
    )
    session.refresh(t)
    assert not ticket_visible(t, copro)
    assert "Lue par défaut" not in (evol.contenu or "")


@pytest.mark.parametrize(
    ("statut", "fermee"),
    [
        ("ouvert", True),
        ("en_cours", True),
        ("en_ag", False),
        ("chez_prestataire", False),
        ("résolu", False),
        ("annulé", False),
    ],
)
def test_une_etude_sort_selon_son_etat(statut, fermee):
    """Ouverte aux copropriétaires, elle peut partir sur le groupe ou au hall —
    si le conseil le demande ; au conseil seul, rien ne sort."""
    t = Ticket(
        numero="T-std",
        titre="Étude",
        description="…",
        categorie="etude_travaux",
        auteur_id=1,
        statut=statut,
        perimetre_cible='["résidence"]',
    )
    assert reservee_au_conseil(t) is fermee
