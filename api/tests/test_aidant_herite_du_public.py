"""L'aidant lit au titre de la personne qu'il aide — et d'elle seule (#1303).

Arbitré le 25/09/2026 : un aidant n'est pas un bailleur, il hérite du droit du
copropriétaire qu'il aide. Éprouvé couple par couple : aidant d'un occupant,
d'un bailleur, et aidant dont la délégation n'est pas (ou plus) active.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import pytest
from sqlmodel import Session, SQLModel

from app.database import engine
from app.models.core import Delegation, StatutDelegation, StatutUtilisateur, Utilisateur
from app.utils import statuts_lus
from app.utils.visibility.socle import public_cible_visible
from tests.purge_test import purger_ligne

OCCUPANTS = json.dumps(["copropriétaires_occupants"], ensure_ascii=False)
BAILLEURS = json.dumps(["bailleurs"], ensure_ascii=False)
CONSEIL = json.dumps(["conseil_syndical"], ensure_ascii=False)


def _compte(session, statut, roles="résident") -> Utilisateur:
    u = Utilisateur(
        email=f"aidant-{uuid.uuid4().hex[:8]}@exemple.test",
        mot_de_passe_hash="x",
        prenom="Camille",
        nom="Sorel",
        roles_json=roles,
        statut=statut,
        actif=True,
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


@pytest.fixture()
def monde():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        crees: list = []

        def compte(statut, roles="résident"):
            u = _compte(session, statut, roles)
            crees.append((Utilisateur, u.id))
            return u

        def deleguer(mandant, aidant, statut=StatutDelegation.active, fin=None):
            d = Delegation(
                mandant_id=mandant.id,
                aidant_id=aidant.id,
                statut=statut,
                date_debut=date.today() - timedelta(days=10),
                date_fin=fin,
                cree_par_id=mandant.id,
            )
            session.add(d)
            session.commit()
            crees.insert(0, (Delegation, d.id))
            statuts_lus.invalider_cache()
            return d

        yield compte, deleguer
        for modele, i in crees:
            purger_ligne(session, modele, i)
        session.commit()
        statuts_lus.invalider_cache()


def test_l_aidant_d_un_occupant_lit_ce_qui_vise_les_occupants(monde):
    compte, deleguer = monde
    occupant = compte(StatutUtilisateur.copropriétaire_résident)
    aidant = compte(StatutUtilisateur.aidant)
    assert not public_cible_visible(OCCUPANTS, aidant), "sans délégation, rien n'est hérité"
    deleguer(occupant, aidant)
    assert public_cible_visible(OCCUPANTS, aidant)
    assert not public_cible_visible(BAILLEURS, aidant), "il hérite de CE statut, pas d'un autre"


def test_l_aidant_d_un_bailleur_lit_ce_qui_vise_les_bailleurs(monde):
    compte, deleguer = monde
    bailleur = compte(StatutUtilisateur.copropriétaire_bailleur)
    aidant = compte(StatutUtilisateur.aidant)
    deleguer(bailleur, aidant)
    assert public_cible_visible(BAILLEURS, aidant)
    assert not public_cible_visible(OCCUPANTS, aidant)


@pytest.mark.parametrize(
    "statut, fin",
    [
        (StatutDelegation.en_attente, None),
        (StatutDelegation.revoquee, None),
        (StatutDelegation.active, date.today() - timedelta(days=1)),
    ],
    ids=["en attente", "révoquée", "échue"],
)
def test_une_delegation_inactive_n_herite_de_rien(monde, statut, fin):
    compte, deleguer = monde
    occupant = compte(StatutUtilisateur.copropriétaire_résident)
    aidant = compte(StatutUtilisateur.aidant)
    deleguer(occupant, aidant, statut=statut, fin=fin)
    assert not public_cible_visible(OCCUPANTS, aidant)


def test_le_role_ne_s_herite_pas(monde):
    """Aider un membre du conseil ne fait pas lire ce que lit le conseil."""
    compte, deleguer = monde
    membre_cs = compte(StatutUtilisateur.copropriétaire_résident, roles="conseil_syndical")
    aidant = compte(StatutUtilisateur.aidant)
    deleguer(membre_cs, aidant)
    assert not public_cible_visible(CONSEIL, aidant)
