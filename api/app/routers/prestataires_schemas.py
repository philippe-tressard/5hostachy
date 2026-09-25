"""Schémas du prestataire — sortis de `routers/prestataires.py` (#1229).

Le routeur approchait les 500 lignes, et le contrôle de la création y ajoutait
un validateur : les schémas partent à côté, comme `annonces_hall_schemas`. Ceux
des contrats et des notations restent dans le routeur, qui les porte seul.
"""

import json
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.core import TypePrestataire
from app.utils.assiste_ia import AssisteIACorrection, AssisteIAEntree, AssisteIASortie


class PrestataireContact(BaseModel):
    telephone: Optional[str] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    fonction: Optional[str] = None
    email: Optional[str] = None


class PrestataireCreate(AssisteIAEntree):
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.ponctuel
    telephone: Optional[str] = None
    email: Optional[str] = None
    #  🔴 FACULTATIFS depuis le 25/09/2026 (#1327) — revirement arbitré à l'écran :
    #  « le contact ne doit pas être obligatoire ». #1229 exigeait la veille un
    #  contact joignable à la création ; la règle et son validateur sont retirés.
    contacts: Optional[list[PrestataireContact]] = None
    adresse: Optional[str] = None
    description: Optional[str] = None


class PrestataireUpdate(AssisteIACorrection):
    nom: Optional[str] = None
    specialite: Optional[str] = None
    type_prestataire: Optional[TypePrestataire] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: Optional[list[PrestataireContact]] = None
    adresse: Optional[str] = None
    description: Optional[str] = None


class PrestataireRead(AssisteIASortie):
    id: int
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.ponctuel
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: list[PrestataireContact] = []
    adresse: Optional[str] = None
    description: Optional[str] = None
    actif: bool

    class Config:
        from_attributes = True

    @field_validator("contacts", mode="before")
    @classmethod
    def parse_contacts(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        if v is None:
            return []
        return v
