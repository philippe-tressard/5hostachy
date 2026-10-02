"""Les schémas d'entrée de l'inscription et de la connexion.

Sortis de `app/schemas.py` (#1566) : un seul routeur s'en sert — `routers/auth.py`
— et une règle du dépôt veut qu'un schéma propre à un seul routeur vive à côté
de lui. `UserRead`, lui, reste dans `schemas.py` : plusieurs routeurs le rendent.
"""

from typing import Optional

from pydantic import BaseModel, field_validator

from app.auth.adresse_compte import normaliser_adresse
from app.models.core import StatutUtilisateur
from app.schemas_communs import nom_en_majuscules


class UserCreate(BaseModel):
    nom: str
    prenom: str
    email: str
    telephone: Optional[str] = None
    societe: Optional[str] = None
    fonction: Optional[str] = None
    password: str
    statut: StatutUtilisateur = StatutUtilisateur.copropriétaire_résident
    consentement_rgpd: bool
    batiment_id: Optional[int] = None
    #  Facultatif : personne n'a à donner son étage pour créer un compte.
    etage: Optional[int] = None
    nom_proprietaire: Optional[str] = None
    nom_aide: Optional[str] = None
    prenom_aide: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str | None) -> str | None:
        return normaliser_adresse(v) if v else v

    @field_validator("nom", "nom_aide", "nom_proprietaire", mode="before")
    @classmethod
    def uppercase_nom(cls, v: str | None) -> str | None:
        return nom_en_majuscules(v)

    @field_validator("prenom", "prenom_aide", mode="before")
    @classmethod
    def titlecase_prenom(cls, v: str | None) -> str | None:
        return v.strip().title() if v else v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return normaliser_adresse(v)
