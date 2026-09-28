"""La location d'un lot — le bail, et les objets remis au locataire.

Extrait de `core.py` le 28/09/2026, au fil de l'eau (#779, modularité). Le
domaine est celui du paquet `routers/bailleur/` (baux, objets, accès), d'où le
nom du module.

Aucune `Relationship` ne sort d'ici : les deux tables ne se lient qu'entre elles,
et `Utilisateur`/`Lot` ne sont visés que par clé étrangère.

Ré-exportées par `core.py` : les imports existants ne bougent pas, et c'est cet
import qui enregistre les tables auprès de SQLModel.
"""

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, Relationship, SQLModel

from app.utils import horloge


class StatutBail(str, Enum):
    actif = "actif"  # locataire en place
    termine = "termine"  # locataire parti
    en_cours_sortie = "en_cours_sortie"  # préavis en cours


class StatutObjet(str, Enum):
    en_possession = "en_possession"  # remis, pas encore rendu
    rendu = "rendu"  # rendu à la sortie
    perdu = "perdu"  # déclaré perdu
    non_remis = "non_remis"  # prévu mais pas encore remis


class TypeObjet(str, Enum):
    cle = "cle"
    telecommande = "telecommande"
    vigik = "vigik"
    autre = "autre"


class LocationBail(SQLModel, table=True):
    """Contrat locatif : lie un bailleur, un locataire (compte ou coordonnées libres) et un lot."""

    __tablename__ = "location_bail"

    id: Optional[int] = Field(default=None, primary_key=True)
    lot_id: int = Field(foreign_key="lot.id", index=True)
    bailleur_id: int = Field(foreign_key="utilisateur.id", index=True)

    # Locataire — soit un compte enregistré, soit des coordonnées libres
    locataire_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    locataire_nom: Optional[str] = None
    locataire_prenom: Optional[str] = None
    locataire_email: Optional[str] = None
    locataire_telephone: Optional[str] = None

    date_entree: date
    date_sortie_prevue: Optional[date] = None
    date_sortie_reelle: Optional[date] = None
    statut: StatutBail = StatutBail.actif
    notes: Optional[str] = None

    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    mis_a_jour_le: NaiveDatetime = Field(default_factory=horloge.maintenant)

    objets: List["RemiseObjet"] = Relationship(back_populates="bail")


class RemiseObjet(SQLModel, table=True):
    """Objet physique remis (ou à remettre) au locataire dans le cadre d'un bail."""

    __tablename__ = "remise_objet"

    id: Optional[int] = Field(default=None, primary_key=True)
    bail_id: int = Field(foreign_key="location_bail.id", index=True)
    type: TypeObjet = TypeObjet.autre
    libelle: str  # ex. "Clé Porte palière", "Télécommande Parking"
    quantite: int = 1
    reference: Optional[str] = None  # ex. "TC-042", "VGK-007"
    statut: StatutObjet = StatutObjet.en_possession
    remis_le: Optional[date] = None
    rendu_le: Optional[date] = None
    notes: Optional[str] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)

    bail: Optional[LocationBail] = Relationship(back_populates="objets")
