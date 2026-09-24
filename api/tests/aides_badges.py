"""Les aides des tests de badges (#1194) — une écriture pour les deux fichiers.

`test_porteurs_acces.py` a dépassé 500 lignes au troisième lot (23/09/2026) :
découpé en deux — la RÈGLE (qui porte, le rattachement) et les GESTES (bail,
commande, parc, suppression) —, les aides vivent ici plutôt que d'être
recopiées dans chacun. `session` est une fixture : un fichier de tests
l'IMPORTE pour que pytest la trouve.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.copropriete import Lot
from app.models.core import LotImport, StatutAcces, StatutImport, UserLot, Utilisateur
from app.utils.types_acces import TELECOMMANDE, VIGIK

TYPES = [pytest.param(TELECOMMANDE, id="telecommande"), pytest.param(VIGIK, id="vigik")]


@pytest.fixture()
def session():
    moteur = create_engine("sqlite://")
    SQLModel.metadata.create_all(moteur)
    with Session(moteur) as s:
        yield s


def _compte(session, nom: str) -> Utilisateur:
    u = Utilisateur(email=f"{nom.lower()}@exemple.fr", hashed_password="x", prenom="P", nom=nom)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def _lot(session, type_acces, numero="12", batiment_id=None) -> Lot:
    lot = Lot(numero=numero, type=type_acces.types_lot[0], batiment_id=batiment_id)
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return lot


def _lier(session, user, lot, type_lien="propriétaire"):
    session.add(UserLot(user_id=user.id, lot_id=lot.id, type_lien=type_lien, actif=True))
    session.commit()


def _badge(
    session,
    type_acces,
    *,
    code="C1",
    lot=None,
    detenteur=None,
    chez_locataire=False,
    statut=StatutAcces.actif,
):
    objet = type_acces.modele(
        code=code,
        lot_id=lot.id if lot else None,
        user_id=detenteur.id if detenteur else None,
        chez_locataire=chez_locataire,
        statut=statut,
    )
    session.add(objet)
    session.commit()
    session.refresh(objet)
    return objet


def _ligne(session, type_acces, *, code="REF-1", lot=None, nom="DUPONT Jean", **extra):
    ligne = type_acces.modele_import(
        nom_proprietaire=nom,
        statut=StatutImport.en_attente,
        lot_id=lot.id if lot else None,
        **extra,
    )
    setattr(ligne, type_acces.colonne_code_import, code)
    session.add(ligne)
    session.commit()
    session.refresh(ligne)
    return ligne


def _copro_du_fichier(session, nom, *lots):
    for lot in lots:
        session.add(
            LotImport(
                numero=lot.numero,
                type_raw="PS",
                no_coproprietaire=nom,
                nom_coproprietaire=nom,
                lot_id=lot.id,
            )
        )
    session.commit()


def _bail(session, lot, bailleur, locataire):
    from datetime import date

    from app.models.core import LocationBail

    bail = LocationBail(
        lot_id=lot.id,
        bailleur_id=bailleur.id,
        locataire_id=locataire.id,
        date_entree=date(2026, 9, 1),
    )
    session.add(bail)
    session.commit()
    session.refresh(bail)
    return bail
