import json
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, field_validator

from app.models.core import StatutUtilisateur, RoleUtilisateur


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
    consentement_communications: bool = False
    batiment_id: Optional[int] = None
    nom_proprietaire: Optional[str] = None
    nom_aide: Optional[str] = None
    prenom_aide: Optional[str] = None

    @field_validator("nom", "nom_aide", "nom_proprietaire", mode="before")
    @classmethod
    def uppercase_nom(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else v

    @field_validator("prenom", "prenom_aide", mode="before")
    @classmethod
    def titlecase_prenom(cls, v: str | None) -> str | None:
        return v.strip().title() if v else v


class UserRead(BaseModel):
    id: int
    nom: str
    prenom: str
    email: str
    telephone: Optional[str] = None
    societe: Optional[str] = None
    fonction: Optional[str] = None
    statut: StatutUtilisateur
    role: RoleUtilisateur
    roles: list[str] = []
    actif: bool
    email_verifie: bool = False
    onboarding_complete: bool
    onboarding_etape: int
    photo_url: Optional[str] = None
    preferences_notifications: str
    demarche_arrivant: Optional[str] = None
    batiment_id: Optional[int] = None
    batiment_nom: Optional[str] = None   # ex. "Bât. A"
    nom_proprietaire: Optional[str] = None
    nom_aide: Optional[str] = None
    prenom_aide: Optional[str] = None
    opt_out_telemetrie: bool = False
    communaute_interdit: bool = False
    communaute_ban_count: int = 0
    communaute_ban_jusqu_au: Optional[datetime] = None
    last_seen_actualites: Optional[datetime] = None
    delegations_aidant: list[dict] = []  # délégations actives où l'utilisateur est aidant
    cree_le: datetime
    derniere_connexion: Optional[datetime] = None

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_with_roles(cls, u, batiment_nom: Optional[str] = None, delegations_aidant: list[dict] | None = None) -> "UserRead":
        data = cls.model_validate(u)
        data.roles = u.roles
        if batiment_nom is not None:
            data.batiment_nom = batiment_nom
        if delegations_aidant is not None:
            data.delegations_aidant = delegations_aidant
        return data


class UserUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    telephone: Optional[str] = None
    societe: Optional[str] = None
    photo_url: Optional[str] = None
    preferences_notifications: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TicketCreate(BaseModel):
    titre: str
    description: str
    categorie: str = "panne"
    lot_id: Optional[int] = None
    batiment_id: Optional[int] = None
    perimetre_cible: Optional[List[str]] = None
    destinataire_syndic: bool = False


class TicketRead(BaseModel):
    id: int
    numero: str
    titre: str
    description: str
    categorie: str
    statut: str
    priorite: str
    auteur_id: int
    auteur_nom: Optional[str] = None
    auteur_batiment_nom: Optional[str] = None
    lot_id: Optional[int] = None
    batiment_id: Optional[int] = None
    perimetre_cible: Optional[List[str]] = None
    photos_urls: Optional[List[str]] = None
    destinataire_syndic: bool = False
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None

    @field_validator('perimetre_cible', mode='before')
    @classmethod
    def parse_perimetre_ticket(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return ['résidence']
        return v

    @field_validator('photos_urls', mode='before')
    @classmethod
    def parse_photos_urls(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v

    class Config:
        from_attributes = True


class TicketUpdate(BaseModel):
    statut: Optional[str] = None
    priorite: Optional[str] = None


class MessageCreate(BaseModel):
    contenu: str
    interne: bool = False


class MessageRead(BaseModel):
    id: int
    ticket_id: int
    auteur_id: int
    contenu: str
    interne: bool
    cree_le: datetime

    class Config:
        from_attributes = True


class TicketEvolutionCreate(BaseModel):
    type: str  # commentaire | etat
    contenu: Optional[str] = None
    nouveau_statut: Optional[str] = None


class TicketEvolutionRead(BaseModel):
    id: int
    ticket_id: int
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int
    auteur_nom: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True


class PublicationCreate(BaseModel):
    titre: str
    contenu: str
    perimetre: str = "résidence"
    batiment_id: Optional[int] = None
    epingle: bool = False
    urgente: bool = False
    image_url: Optional[str] = None
    perimetre_cible: List[str] = ["résidence"]
    public_cible: List[str] = ["résidents"]
    statut: Optional[str] = None
    brouillon: bool = False
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False


class PublicationUpdate(BaseModel):
    titre: Optional[str] = None
    contenu: Optional[str] = None
    epingle: Optional[bool] = None
    urgente: Optional[bool] = None
    perimetre_cible: Optional[List[str]] = None
    public_cible: Optional[List[str]] = None
    statut: Optional[str] = None
    brouillon: Optional[bool] = None
    archivee: Optional[bool] = None
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None


class EvolutionRead(BaseModel):
    id: int
    publication_id: int
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int
    auteur_nom: Optional[str] = None
    cree_le: datetime

    class Config:
        from_attributes = True


class EvolutionCreate(BaseModel):
    type: str  # commentaire | etat | correction
    contenu: Optional[str] = None
    nouveau_statut: Optional[str] = None  # requis si type=="etat"
    partager_whatsapp: Optional[bool] = None  # None = hérite de la publication
    envoyer_syndic: Optional[bool] = None  # None = hérite de la publication


class PublicationRead(BaseModel):
    id: int
    titre: str
    contenu: str
    perimetre: str
    batiment_id: Optional[int] = None
    epingle: bool
    urgente: bool
    auteur_id: int
    image_url: Optional[str] = None
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None
    perimetre_cible: List[str] = ["résidence"]
    public_cible: List[str] = ["résidents"]
    statut: Optional[str] = None
    statut_change_le: Optional[datetime] = None
    brouillon: bool = False
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    evolutions: List[EvolutionRead] = []
    auteur_nom: Optional[str] = None

    @field_validator('perimetre_cible', 'public_cible', mode='before')
    @classmethod
    def parse_json_list(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [v] if v else []
        return v or []

    class Config:
        from_attributes = True


class DocumentRead(BaseModel):
    id: int
    titre: str
    fichier_nom: str
    taille_octets: Optional[int] = None
    mime_type: str
    categorie_id: Optional[int] = None
    contrat_id: Optional[int] = None
    perimetre: str
    batiment_id: Optional[int] = None
    publie_le: datetime
    annee: Optional[int] = None
    date_ag: Optional[date] = None
    batiments_ids_json: Optional[str] = None

    class Config:
        from_attributes = True


class NotificationRead(BaseModel):
    id: int
    type: str
    titre: str
    corps: str
    lien: Optional[str] = None
    lue: bool
    urgente: bool
    cree_le: datetime

    class Config:
        from_attributes = True


class CommandeAccesCreate(BaseModel):
    lot_id: int
    type: str  # vigik | telecommande
    quantite: int = 1
    motif: Optional[str] = None


class CommandeAccesRead(BaseModel):
    id: int
    user_id: int
    lot_id: int
    type: str
    quantite: int
    motif: Optional[str] = None
    statut: str
    cree_le: datetime

    class Config:
        from_attributes = True
