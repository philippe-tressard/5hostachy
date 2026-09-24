"""Schémas du prestataire — sortis de `routers/prestataires.py` (#1229).

Le routeur approchait les 500 lignes, et le contrôle de la création y ajoutait
un validateur : les schémas partent à côté, comme `annonces_hall_schemas`. Ceux
des contrats et des notations restent dans le routeur, qui les porte seul.
"""

import json
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.core import TypePrestataire


def contact_joignable(contact: "PrestataireContact") -> bool:
    """Un nom, et un moyen de le joindre — la règle de #1229, écrite une fois."""
    return bool(
        (contact.nom or "").strip()
        and ((contact.telephone or "").strip() or (contact.email or "").strip())
    )


class PrestataireContact(BaseModel):
    telephone: Optional[str] = None
    prenom: Optional[str] = None
    nom: Optional[str] = None
    fonction: Optional[str] = None
    email: Optional[str] = None


class PrestataireCreate(BaseModel):
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.ponctuel
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: Optional[list[PrestataireContact]] = None

    #  🔴 Un contact JOIGNABLE à la création (#1229, arbitré le 24/09/2026) : un
    #  nom, et un téléphone OU un e-mail. Seulement ici — `PrestataireUpdate`
    #  ne l'exige pas, les fiches existantes se corrigent sans être bloquées.
    @field_validator("contacts")
    @classmethod
    def un_contact_joignable(cls, v):
        if not any(contact_joignable(c) for c in (v or [])):
            raise ValueError("un contact au moins : son nom, et un téléphone ou un e-mail")
        return v


class PrestataireUpdate(BaseModel):
    nom: Optional[str] = None
    specialite: Optional[str] = None
    type_prestataire: Optional[TypePrestataire] = None
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: Optional[list[PrestataireContact]] = None


class PrestataireRead(BaseModel):
    id: int
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.ponctuel
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts: list[PrestataireContact] = []
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
