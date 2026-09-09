"""L'étage se modifie depuis le profil, et le serveur le borne (#835, 08/09/2026).

## L'arbitrage

Le changement de **bâtiment** passe par `demanderModification`, approuvé par le
conseil : il touche à ce qu'on est dans la copropriété. L'**étage** ne revendique
rien — c'est un repère de voisinage, comme le téléphone. Il se modifie donc
directement (arbitrage du 08/09/2026).

## 🔴 Pourquoi le serveur borne, et pas seulement l'écran

Le champ porte `min="-2" max="50"` dans les deux formulaires. Un champ borné côté
client **se poste directement** : `PATCH /auth/me` est une route comme une autre.
Un étage à 4 000 n'est pas une donnée, c'est une faute de frappe — et il
s'imprimerait dans l'annonce de bienvenue publiée à l'arrivée d'un résident.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import Utilisateur
from app.routers.auth_profil import MeUpdate, update_me


@pytest.fixture()
def compte():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = Utilisateur(
            email=f"e-{uuid.uuid4().hex[:8]}@exemple.test", mot_de_passe_hash="x",
            prenom="Alix", nom="RIVANT", roles_json="résident", actif=True, etage=2,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        yield session, user
        session.delete(user)
        session.commit()


def test_l_etage_se_modifie_SANS_validation_du_conseil(compte):
    """🔴 Le geste demandé — et il aboutit en base, pas dans une demande."""
    session, user = compte

    update_me(MeUpdate(etage=5), BackgroundTasks(), session=session, user=user)

    session.refresh(user)
    assert user.etage == 5, "l'étage n'a pas été enregistré"


@pytest.mark.parametrize("valeur", [-2, 0, 50], ids=["sous-sol", "RDC", "plafond"])
def test_les_BORNES_sont_acceptees(compte, valeur):
    """Les extrêmes légitimes passent — un contrôle qui refuse le licite se désarme."""
    session, user = compte
    update_me(MeUpdate(etage=valeur), BackgroundTasks(), session=session, user=user)
    session.refresh(user)
    assert user.etage == valeur


@pytest.mark.parametrize("valeur", [-3, 51, 4000], ids=["trop-bas", "trop-haut", "frappe"])
def test_une_valeur_HORS_BORNES_est_refusee(compte, valeur):
    """🔴 Le contrôle vit côté SERVEUR : le champ borné de l'écran se contourne.

    Un étage à 4 000 s'imprimerait dans l'annonce de bienvenue publiée à
    l'arrivée d'un résident.
    """
    session, user = compte
    with pytest.raises(HTTPException) as capture:
        update_me(MeUpdate(etage=valeur), BackgroundTasks(), session=session, user=user)
    assert capture.value.status_code == 400
    session.refresh(user)
    assert user.etage == 2, "la valeur refusée a quand même été écrite"


def test_ne_PAS_envoyer_l_etage_ne_l_efface_pas(compte):
    """Cas zéro : un `PATCH` partiel qui n'en parle pas ne doit rien changer.

    ⚠️ C'est le piège de tout `PATCH` : `None` veut dire « je n'en parle pas »,
    pas « efface ». Un formulaire qui enregistre le téléphone seul viderait sinon
    l'étage sans que personne ne l'ait demandé.
    """
    session, user = compte
    update_me(MeUpdate(telephone="+33 6 00 00 00 00"), BackgroundTasks(), session=session, user=user)
    session.refresh(user)
    assert user.etage == 2, "l'étage a été effacé par une mise à jour qui l'ignorait"
