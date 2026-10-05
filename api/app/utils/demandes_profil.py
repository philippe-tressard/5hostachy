"""Une demande de modification de profil, lue UNE fois (#1686, #1696).

La ligne `demande_modification_profil`, plus le libellé du bâtiment souhaité.
Trois routes la rendent : la création et la liste du résident
(`routers/auth_profil.py`), la file du conseil (`routers/admin/profils.py`), qui
y ajoute ce qui identifie le demandeur. Le libellé était composé à la main par
deux d'entre elles, et la création l'oubliait (#1686).

Ici et non dans un routeur : les deux en ont besoin, et un routeur qui en
importe un autre n'est plus un routeur. 🔒 test_demande_modification_profil.py
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlmodel import Session

from app.models.copropriete import Batiment
from app.models.validations import DemandeModificationProfil, StatutDemandeProfil
from app.utils.batiments import libelle_batiment_ou
from app.utils.lecture import lire_objet


class DemandeModifRead(BaseModel):
    """Une demande : la ligne, plus le libellé du bâtiment souhaité."""

    id: int
    utilisateur_id: int
    statut_souhaite: str | None = None
    batiment_id_souhaite: int | None = None
    motif: str | None = None
    statut_demande: StatutDemandeProfil
    motif_refus: str | None = None
    traite_par_id: int | None = None
    cree_le: datetime
    traite_le: datetime | None = None
    batiment_nom_souhaite: str | None = None

    class Config:
        from_attributes = True


def lire_demande(session: Session, demande: DemandeModificationProfil) -> DemandeModifRead:
    """La lecture de la création, de la liste du résident et de la file du conseil.

    Le libellé du bâtiment n'était composé que par la liste : une demande tout
    juste déposée n'affichait pas « déménagement vers … » avant un rechargement.
    """
    bat_id = demande.batiment_id_souhaite
    bat = session.get(Batiment, bat_id) if bat_id else None
    return lire_objet(
        DemandeModifRead, demande, batiment_nom_souhaite=libelle_batiment_ou(bat, None)
    )
