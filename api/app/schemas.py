import json
from datetime import datetime, date
from typing import Annotated, Optional, List
from pydantic import BaseModel, BeforeValidator, field_validator

from app.models.core import StatutUtilisateur, RoleUtilisateur


def _liste_depuis_json(v):
    """Colonne texte contenant un tableau JSON → liste d'URLs.

    Quatre schémas portaient ce même validateur recopié (`photos_urls`,
    `fichiers_urls` × 3). C'est la contrepartie côté pydantic de
    `app/utils/photos.parse_photos`, que les routeurs utilisent pour lire les
    mêmes colonnes : deux points d'entrée, une seule règle.

    Ne lève jamais : une valeur illisible en base ne doit pas faire échouer la
    lecture de l'élément qui la porte. Le pire cas est une liste vide.
    """
    if v is None:
        return []
    if isinstance(v, str):
        try:
            charge = json.loads(v)
        except Exception:
            return []
        return [str(u) for u in charge] if isinstance(charge, list) else []
    return v


#: Champ exposé en liste, stocké en colonne texte. `Optional[ListeUrls]` reste
#: possible là où l'absence et la liste vide doivent se distinguer.
ListeUrls = Annotated[List[str], BeforeValidator(_liste_depuis_json)]


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

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str | None) -> str | None:
        return v.strip().lower() if v else v

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
    #  Préférence d'AFFICHAGE, jamais un droit — cf. models/core.py.
    restreindre_a_mes_batiments: bool = False
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
    restreindre_a_mes_batiments: Optional[bool] = None


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


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
    destinataire_cs: bool = False
    #  Troisième canal, aligné sur les actualités, le calendrier et les sondages.
    #  Il manquait ici et NULLE PART ailleurs : un ticket ne pouvait être partagé
    #  sur le groupe qu'après coup, via un commentaire (signalé le 08/08/2026).
    #  Comme `destinataire_*`, c'est une intention d'envoi et non un état du
    #  ticket : rien n'est stocké sur le modèle.
    partager_whatsapp: bool = False
    saisi_pour_user_id: Optional[int] = None
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement
    # Pièces jointes déjà téléversées via POST /uploads/fichier — photos et
    # documents. Les fournir DÈS la création, et non après, est ce qui permet à
    # l'e-mail syndic/CS de partir avec : il est construit dans la foulée.
    # Filtrées par `photos_internes` côté routeur : le client ne choisit pas
    # quelle URL est jointe, il ne peut que désigner nos propres fichiers.
    photos_urls: List[str] = []
    fichiers_urls: List[str] = []


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
    photos_urls: Optional[ListeUrls] = None
    fichiers_urls: ListeUrls = []
    destinataire_syndic: bool = False
    destinataire_cs: bool = False
    saisi_pour_user_id: Optional[int] = None
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None
    saisi_pour_affichage: Optional[str] = None
    non_relancable: bool = False
    non_relancable_motif: Optional[str] = None
    relance_count: int = 0
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

    class Config:
        from_attributes = True


class TicketUpdate(BaseModel):
    statut: Optional[str] = None
    priorite: Optional[str] = None
    titre: Optional[str] = None
    description: Optional[str] = None
    categorie: Optional[str] = None
    perimetre_cible: Optional[List[str]] = None
    lot_id: Optional[int] = None
    batiment_id: Optional[int] = None
    destinataire_syndic: Optional[bool] = None
    destinataire_cs: Optional[bool] = None
    saisi_pour_user_id: Optional[int] = None
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None
    non_relancable: Optional[bool] = None
    non_relancable_motif: Optional[str] = None
    # Sert à retirer ou réordonner des pièces jointes déjà téléversées : l'ajout
    # passe par POST /uploads/fichier, seul endroit qui valide le type MIME.
    fichiers_urls: Optional[List[str]] = None


class MessageCreate(BaseModel):
    contenu: str
    interne: bool = False
    fichiers_urls: List[str] = []
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement


class MessageRead(BaseModel):
    id: int
    ticket_id: int
    auteur_id: int
    contenu: str
    interne: bool
    cree_le: datetime
    fichiers_urls: ListeUrls = []

    class Config:
        from_attributes = True


class TicketEvolutionCreate(BaseModel):
    type: str  # commentaire | etat
    contenu: Optional[str] = None
    nouveau_statut: Optional[str] = None
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None
    envoyer_cs: Optional[bool] = None
    fichiers_urls: List[str] = []
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement


class TicketEvolutionUpdate(BaseModel):
    contenu: Optional[str] = None
    fichiers_urls: Optional[List[str]] = None


class PublicationEvolutionUpdate(BaseModel):
    contenu: Optional[str] = None
    fichiers_urls: Optional[List[str]] = None


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
    fichiers_urls: ListeUrls = []

    class Config:
        from_attributes = True


class PublicationCreate(BaseModel):
    titre: str
    contenu: str
    perimetre: str = "résidence"
    batiment_id: Optional[int] = None
    epingle: bool = False
    urgente: bool = False
    photos_urls: ListeUrls = []
    perimetre_cible: List[str] = ["résidence"]
    public_cible: List[str] = ["résidents"]
    statut: Optional[str] = "publie"
    brouillon: bool = False
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False
    annonce_hall: bool = False  # génère l'affiche de hall + envoi au CS du périmètre
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement


class PublicationUpdate(BaseModel):
    titre: Optional[str] = None
    contenu: Optional[str] = None
    epingle: Optional[bool] = None
    urgente: Optional[bool] = None
    photos_urls: Optional[ListeUrls] = None
    batiment_id: Optional[int] = None
    perimetre_cible: Optional[List[str]] = None
    public_cible: Optional[List[str]] = None
    statut: Optional[str] = None
    brouillon: Optional[bool] = None
    archivee: Optional[bool] = None
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None
    envoyer_cs: Optional[bool] = None
    annonce_hall: Optional[bool] = None


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
    fichiers_urls: ListeUrls = []

    class Config:
        from_attributes = True


class EvolutionCreate(BaseModel):
    type: str  # commentaire | etat | correction
    contenu: Optional[str] = None
    nouveau_statut: Optional[str] = None  # requis si type=="etat"
    partager_whatsapp: Optional[bool] = None  # None = hérite de la publication
    envoyer_syndic: Optional[bool] = None  # None = hérite de la publication
    envoyer_cs: Optional[bool] = None  # None = hérite de la publication
    fichiers_urls: List[str] = []
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement


class PublicationRead(BaseModel):
    id: int
    titre: str
    contenu: str
    perimetre: str
    batiment_id: Optional[int] = None
    epingle: bool
    urgente: bool
    auteur_id: int
    photos_urls: ListeUrls = []
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None
    perimetre_cible: List[str] = ["résidence"]
    public_cible: List[str] = ["résidents"]
    statut: Optional[str] = None
    statut_change_le: Optional[datetime] = None
    brouillon: bool = False
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False
    annonce_hall: bool = False
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
    publication_id: Optional[int] = None
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
