"""Un lot d'événements s'écrit en entier, ou pas du tout — et ne diffuse jamais.

## 🔴 Pourquoi (#605 point 3, 01/09/2026)

Le pré-remplissage du kanban par les prestataires écrivait **en boucle depuis le
navigateur** :

    for (const ev of plan.aCreer) await calApi.create(ev);

Un échec au 7ᵉ sur 20 laissait **six** événements créés, et l'écran affichait
« Erreur lors de l'initialisation » sans dire lesquels. Le second passage en
ignorait une partie — mais seulement si aucun titre n'avait bougé, la clé
anti-doublon étant le titre littéral (point 2 du ticket, toujours ouvert).

`POST /calendrier/lot` appelle `session.commit()` **une seule fois** : soit les
vingt existent, soit aucun.

## Et ce que ce point d'entrée refuse

Un lot est un pré-remplissage **silencieux**. En faire un canal, c'est offrir
l'envoi de cent courriels ou messages WhatsApp en une requête. Deux refus
explicites plutôt qu'un silence :

- les **canaux de diffusion** — les ignorer serait pire, l'appelant croirait
  avoir diffusé ;
- les types **coupure** et **travaux**, qui notifient tous les résidents à la
  création unitaire. Les accepter ici sans notifier produirait deux comportements
  pour un même type selon le point d'entrée employé.

⚠️ Ces tests appellent la fonction du routeur **directement**, comme
`test_calendrier_suivi_notifie` : ce qu'on vérifie est ce que la base contient
après coup, pas un code HTTP (`standards/04` §14 — observer la chose, pas son
enregistrement).
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, select

from app.database import engine
from app.models.core import Evenement, RoleUtilisateur, TypeEvenement, Utilisateur
from app.routers.calendrier import (
    LOT_MAX,
    EvenementCreate,
    EvenementsLot,
    create_evenements_lot,
)
from tests.purge_test import purger_ligne


@pytest.fixture()
def cs():
    """Un membre du conseil syndical — le seul rôle autorisé à créer un lot."""
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = Utilisateur(
            email=f"cs-{uuid.uuid4().hex[:8]}@exemple.test",
            mot_de_passe_hash="x",
            prenom="Camille",
            nom="Sorel",
            role=RoleUtilisateur.conseil_syndical,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        yield user
        for ev in session.exec(
            select(Evenement).where(Evenement.auteur_id == user.id)
        ).all():
            purger_ligne(session, Evenement, ev.id)
        purger_ligne(session, Utilisateur, user.id)
        session.commit()


def _visite(n: int, **extra) -> EvenementCreate:
    """Une visite de maintenance telle que le pré-remplissage la fabrique."""
    return EvenementCreate(
        titre=f"Entretien chaudière — visite {n}/4",
        type=TypeEvenement.maintenance_recurrente,
        debut=datetime(2026, 3 * n, 15, 9, 0),
        statut_kanban="fournisseur",
        affichable=False,
        **extra,
    )


def _compter(session: Session, user: Utilisateur) -> int:
    return len(
        session.exec(select(Evenement).where(Evenement.auteur_id == user.id)).all()
    )


def test_un_lot_valide_cree_tous_les_evenements(cs):
    with Session(engine) as session:
        avant = _compter(session, cs)
        lot = EvenementsLot(evenements=[_visite(n) for n in (1, 2, 3, 4)])
        rendus = create_evenements_lot(lot, session=session, user=cs)

        assert len(rendus) == 4
        assert _compter(session, cs) == avant + 4
        #  Le pré-remplissage crée des cartes de colonne « Fournisseur », qui ne
        #  s'affichent pas dans le calendrier public : le lot doit les préserver
        #  telles quelles, sinon vingt événements surgiraient sur l'agenda.
        for ev in rendus:
            assert ev.statut_kanban == "fournisseur"


def test_un_lot_vide_est_refuse(cs):
    """Le cas zéro : rien à écrire n'est pas un succès, c'est un appel fautif."""
    with Session(engine) as session:
        with pytest.raises(HTTPException) as e:
            create_evenements_lot(EvenementsLot(evenements=[]), session=session, user=cs)
        assert e.value.status_code == 422


def test_un_lot_trop_grand_est_refuse(cs):
    """Le plafond existe pour qu'une requête forgée n'écrive pas dix mille lignes."""
    with Session(engine) as session:
        avant = _compter(session, cs)
        lot = EvenementsLot(evenements=[_visite(1) for _ in range(LOT_MAX + 1)])
        with pytest.raises(HTTPException) as e:
            create_evenements_lot(lot, session=session, user=cs)
        assert e.value.status_code == 422
        assert _compter(session, cs) == avant, "un lot refusé n'écrit rien"


@pytest.mark.parametrize(
    "canal",
    ["partager_whatsapp", "envoyer_syndic", "envoyer_cs", "envoyer_auteur"],
)
def test_un_lot_qui_demande_a_diffuser_est_refuse(cs, canal):
    """🔴 Refusé, et non ignoré : l'appelant croirait sinon avoir diffusé.

    C'est le défaut du triple envoi WhatsApp en sens inverse — une intention
    d'envoi que le serveur ne consomme pas, et que rien ne signale.
    """
    with Session(engine) as session:
        avant = _compter(session, cs)
        lot = EvenementsLot(evenements=[_visite(1), _visite(2, **{canal: True})])
        with pytest.raises(HTTPException) as e:
            create_evenements_lot(lot, session=session, user=cs)
        assert e.value.status_code == 422
        #  ⚠️ Le premier événement du lot était valide : c'est LUI qui prouve
        #  l'atomicité. Sans cette assertion, le test passerait aussi sur une
        #  implémentation qui écrit jusqu'au fautif puis s'arrête.
        assert _compter(session, cs) == avant, "le lot doit être tout ou rien"


@pytest.mark.parametrize("type_notifiant", [TypeEvenement.coupure, TypeEvenement.travaux])
def test_un_lot_refuse_les_types_qui_notifient(cs, type_notifiant):
    """Deux comportements pour un même type selon le point d'entrée : jamais.

    La création unitaire notifie TOUS les résidents pour ces deux types. Les
    accepter ici sans notifier rendrait le comportement dépendant de la route
    employée, ce que personne ne pourrait deviner depuis l'écran.
    """
    with Session(engine) as session:
        avant = _compter(session, cs)
        lot = EvenementsLot(
            evenements=[
                EvenementCreate(
                    titre="Coupure d'eau",
                    type=type_notifiant,
                    debut=datetime(2026, 4, 2, 8, 0),
                )
            ]
        )
        with pytest.raises(HTTPException) as e:
            create_evenements_lot(lot, session=session, user=cs)
        assert e.value.status_code == 422
        assert _compter(session, cs) == avant


def test_les_pieces_jointes_externes_sont_ecartees(cs):
    """Même règle que la création unitaire — et c'est la raison d'être du test.

    Une pièce jointe pointant vers un site tiers révélerait l'IP de chaque
    lecteur, avec un contenu hors de notre contrôle. `photos_internes` l'écarte
    à la création unitaire ; un second point d'entrée qui l'oublierait rouvrirait
    la porte par un chemin que personne ne regarde.
    """
    with Session(engine) as session:
        lot = EvenementsLot(
            evenements=[
                _visite(
                    1,
                    photos_urls=["https://exemple-tiers.test/pixel.jpg", "/uploads/a.jpg"],
                )
            ]
        )
        (rendu,) = create_evenements_lot(lot, session=session, user=cs)
        ev = session.get(Evenement, rendu.id)
        assert "exemple-tiers" not in (ev.photos_urls or "")
        assert "/uploads/a.jpg" in (ev.photos_urls or "")
