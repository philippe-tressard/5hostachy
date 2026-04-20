"""
Modèles SQLModel — version 0.1
Correspond au modèle de données défini dans specs/architecture/modele-donnees.md
"""
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


# ──────────────────────────────────────────────
#  Enums
# ──────────────────────────────────────────────

class StatutUtilisateur(str, Enum):
    copropriétaire_résident = "copropriétaire_résident"
    copropriétaire_bailleur = "copropriétaire_bailleur"
    locataire = "locataire"
    syndic = "syndic"
    mandataire = "mandataire"
    aidant = "aidant"   # proche aidant (famille) — accès délégué, pas de vote AG
    admin_technique = "admin_technique"  # compte technique sans lot ni statut résidentiel


class StatutDelegation(str, Enum):
    en_attente = "en_attente"       # créée par le CS, en attente d'acceptation
    active = "active"               # acceptée par l'aidant
    revoquee = "revoquee"           # révoquée par le mandant ou le CS
    expiree = "expiree"             # date de fin dépassée


class RoleUtilisateur(str, Enum):
    propriétaire = "propriétaire"
    résident = "résident"
    externe = "externe"
    conseil_syndical = "conseil_syndical"
    admin = "admin"


class TypeLot(str, Enum):
    appartement = "appartement"
    cave = "cave"
    parking = "parking"


class TypeLien(str, Enum):
    propriétaire = "propriétaire"   # copropriétaire résident (occupe le lot)
    bailleur     = "bailleur"       # copropriétaire non-résident (loue le lot)
    locataire    = "locataire"      # locataire d'un bailleur
    mandataire   = "mandataire"     # mandataire de gestion (se substitue au bailleur)


class StatutTicket(str, Enum):
    ouvert = "ouvert"
    en_cours = "en_cours"
    résolu = "résolu"
    annulé = "annulé"
    fermé = "fermé"  # conservé pour compatibilité données existantes


class CategorieTicket(str, Enum):
    panne = "panne"
    nuisance = "nuisance"
    question = "question"
    urgence = "urgence"
    bug = "bug"


class PrioriteTicket(str, Enum):
    basse = "basse"
    normale = "normale"
    haute = "haute"


class TypePrestataire(str, Enum):
    contrat_recurrent = "contrat_recurrent"
    ponctuel = "ponctuel"
    travaux = "travaux"
    reglementaire = "reglementaire"
    etudes_expertise = "etudes_expertise"
    gestion = "gestion"


class StatutDevis(str, Enum):
    en_attente = "en_attente"
    accepte = "accepte"
    refuse = "refuse"
    realise = "realise"


class TypeEquipement(str, Enum):
    ascenseur = "ascenseur"
    chauffage_collectif = "chauffage_collectif"
    eau = "eau"
    electricite = "electricite"
    espaces_verts = "espaces_verts"
    extincteurs = "extincteurs"
    interphone_digicode = "interphone_digicode"
    nettoyage = "nettoyage"
    plomberie = "plomberie"
    pompe = "pompe"
    porte_parking = "porte_parking"
    serrurerie = "serrurerie"
    toiture = "toiture"
    vmc = "vmc"
    autre = "autre"


class StatutSauvegarde(str, Enum):
    en_cours = "en_cours"
    reussie = "reussie"
    echouee = "echouee"


# ──────────────────────────────────────────────
#  FAQ
# ──────────────────────────────────────────────

class FaqItem(SQLModel, table=True):
    __tablename__ = "faq_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    categorie: str          # ex. "🗑️ Tri des déchets"
    question: str
    reponse: str
    ordre: int = 0          # ordre d'affichage dans la catégorie
    actif: bool = True
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: datetime = Field(default_factory=datetime.utcnow)


class FrequenceSauvegarde(str, Enum):
    quotidienne = "quotidienne"
    hebdomadaire = "hebdomadaire"
    mensuelle = "mensuelle"


# ──────────────────────────────────────────────
#  Copropriété
# ──────────────────────────────────────────────

class Copropriete(SQLModel, table=True):
    __tablename__ = "copropriete"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    adresse: str
    annee_construction: Optional[int] = None
    nb_lots_total: Optional[int] = None
    numero_immatriculation: Optional[str] = None  # ANAH/ALUR
    assurance_compagnie: Optional[str] = None
    assurance_numero_police: Optional[str] = None
    assurance_echeance: Optional[date] = None
    photo_url: Optional[str] = None
    nb_parkings_communs: int = 0

    batiments: List["Batiment"] = Relationship(back_populates="copropriete")
    contrats_entretien: List["ContratEntretien"] = Relationship(back_populates="copropriete")


class Batiment(SQLModel, table=True):
    __tablename__ = "batiment"
    id: Optional[int] = Field(default=None, primary_key=True)
    copropriete_id: int = Field(foreign_key="copropriete.id")
    numero: str  # A, B, C, D…
    nb_etages: int = 0
    sous_sol: bool = False
    specificites: Optional[str] = None
    nb_appartements: int = 0
    nb_caves: int = 0
    nb_parkings: int = 0
    nb_locaux_commerciaux: int = 0

    copropriete: Optional[Copropriete] = Relationship(back_populates="batiments")
    lots: List["Lot"] = Relationship(back_populates="batiment")


class Lot(SQLModel, table=True):
    __tablename__ = "lot"
    id: Optional[int] = Field(default=None, primary_key=True)
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")  # None pour les parkings
    numero: str
    type: TypeLot = TypeLot.appartement
    type_appartement: Optional[str] = None  # Studio, T1, T2…
    etage: Optional[int] = None
    superficie: Optional[float] = None

    batiment: Optional[Batiment] = Relationship(back_populates="lots")
    user_lots: List["UserLot"] = Relationship(back_populates="lot")
    tickets: List["Ticket"] = Relationship(back_populates="lot")


# ──────────────────────────────────────────────
#  Utilisateurs
# ──────────────────────────────────────────────

class Utilisateur(SQLModel, table=True):
    __tablename__ = "utilisateur"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    prenom: str
    email: str = Field(unique=True, index=True)
    telephone: Optional[str] = None
    hashed_password: Optional[str] = None
    statut: StatutUtilisateur = StatutUtilisateur.copropriétaire_résident
    role: RoleUtilisateur = RoleUtilisateur.résident  # rôle principal (legacy + fallback)
    roles_json: str = Field(default="")  # rôles cumulés, virgule-séparés : "résident,conseil_syndical"
    actif: bool = Field(default=False)  # False = en attente de validation
    email_verifie: bool = Field(default=False)  # False = email non confirmé
    onboarding_complete: bool = False
    onboarding_etape: int = 0  # 0-4
    photo_url: Optional[str] = None
    societe: Optional[str] = None
    fonction: Optional[str] = None
    consentement_rgpd: bool = False
    consentement_communications: bool = False
    opt_out_telemetrie: bool = Field(default=False)
    communaute_interdit: bool = Field(default=False)  # ban permanent (2e infraction)
    communaute_ban_count: int = Field(default=0)  # 0=jamais banni, 1=1er ban, 2+=permanent
    communaute_ban_jusqu_au: Optional[datetime] = Field(default=None)  # fin du ban temporaire
    preferences_notifications: str = Field(default='{"ticket_app":true,"ticket_mail":true,"actu_app":true,"actu_mail":true,"doc_app":true,"doc_mail":false}')
    demarche_arrivant: Optional[str] = Field(default=None)  # nouvel_arrivant | deja_resident | None
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    nom_proprietaire: Optional[str] = None  # pour les locataires : nom du propriétaire bailleur
    nom_aide: Optional[str] = None      # pour aidant/mandataire : nom du copropriétaire aidé
    prenom_aide: Optional[str] = None   # pour aidant/mandataire : prénom du copropriétaire aidé
    last_seen_actualites: Optional[datetime] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    derniere_connexion: Optional[datetime] = None

    user_lots: List["UserLot"] = Relationship(back_populates="utilisateur")

    # ── Gestion multi-rôles ──────────────────────────────────────────────────

    @property
    def roles(self) -> list[str]:
        """Liste des rôles de cet utilisateur (depuis roles_json, fallback sur role)."""
        if not self.roles_json:
            v = self.role.value if hasattr(self.role, "value") else str(self.role)
            return [v]
        return [r.strip() for r in self.roles_json.split(",") if r.strip()]

    def has_role(self, *roles: "RoleUtilisateur") -> bool:
        """Retourne True si l'utilisateur possède au moins un des rôles donnés."""
        user_roles = self.roles
        for r in roles:
            rv = r.value if hasattr(r, "value") else str(r)
            if rv in user_roles:
                return True
        return False

    def ajouter_role(self, role: "RoleUtilisateur") -> None:
        """Ajoute un rôle sans doublon. Met aussi à jour `role` (rôle principal)."""
        rv = role.value if hasattr(role, "value") else str(role)
        current = self.roles
        if rv not in current:
            current.append(rv)
        self.roles_json = ",".join(current)
        # Le rôle principal est le "plus élevé" : admin > conseil_syndical > propriétaire > résident/externe
        _priority = {RoleUtilisateur.admin: 4, RoleUtilisateur.conseil_syndical: 3, RoleUtilisateur.propriétaire: 2, RoleUtilisateur.résident: 1, RoleUtilisateur.externe: 1}

        def _rank(r_str: str) -> int:
            try:
                return _priority.get(RoleUtilisateur(r_str), 0)
            except ValueError:
                return 0

        top = max(current, key=_rank, default=rv)
        try:
            self.role = RoleUtilisateur(top)
        except ValueError:
            pass

    def retirer_role(self, role: "RoleUtilisateur") -> None:
        """Retire un rôle. Garde au minimum 'résident'."""
        rv = role.value if hasattr(role, "value") else str(role)
        current = [r for r in self.roles if r != rv]
        if not current:
            current = [RoleUtilisateur.résident.value]
        self.roles_json = ",".join(current)
        _priority = {RoleUtilisateur.admin: 4, RoleUtilisateur.conseil_syndical: 3, RoleUtilisateur.propriétaire: 2, RoleUtilisateur.résident: 1, RoleUtilisateur.externe: 1}

        def _rank(r_str: str) -> int:
            try:
                return _priority.get(RoleUtilisateur(r_str), 0)
            except ValueError:
                return 0

        top = max(current, key=_rank, default=RoleUtilisateur.résident.value)
        try:
            self.role = RoleUtilisateur(top)
        except ValueError:
            pass
    tickets: List["Ticket"] = Relationship(back_populates="auteur")
    publications: List["Publication"] = Relationship(back_populates="auteur")


class UserLot(SQLModel, table=True):
    __tablename__ = "user_lot"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    lot_id: int = Field(foreign_key="lot.id")
    type_lien: TypeLien = TypeLien.propriétaire
    quote_part: Optional[float] = None  # en millièmes
    actif: bool = True

    utilisateur: Optional[Utilisateur] = Relationship(back_populates="user_lots")
    lot: Optional[Lot] = Relationship(back_populates="user_lots")


class Mandat(SQLModel, table=True):
    __tablename__ = "mandat"
    id: Optional[int] = Field(default=None, primary_key=True)
    mandataire_id: int = Field(foreign_key="utilisateur.id")
    bailleur_id: int = Field(foreign_key="utilisateur.id")
    lot_id: int = Field(foreign_key="lot.id")
    type_mandat: str = "location"  # location | juridique
    date_debut: date = Field(default_factory=date.today)
    date_fin: Optional[date] = None
    actif: bool = True


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    revoked: bool = False


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    used: bool = False


class EmailVerificationToken(SQLModel, table=True):
    __tablename__ = "email_verification_token"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    used: bool = False


# ──────────────────────────────────────────────
#  Accès (Vigik / Télécommandes)
# ──────────────────────────────────────────────

class StatutCommande(str, Enum):
    en_attente = "en_attente"
    acceptee = "acceptee"
    refusee = "refusee"


class CommandeAcces(SQLModel, table=True):
    __tablename__ = "commande_acces"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    lot_id: int = Field(foreign_key="lot.id")
    type: str  # vigik | telecommande
    quantite: int = 1
    motif: Optional[str] = None
    statut: StatutCommande = StatutCommande.en_attente
    traite_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    motif_refus: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    traite_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Tickets
# ──────────────────────────────────────────────

class Ticket(SQLModel, table=True):
    __tablename__ = "ticket"
    id: Optional[int] = Field(default=None, primary_key=True)
    numero: str = Field(unique=True, index=True)
    titre: str
    description: str
    categorie: CategorieTicket = CategorieTicket.panne
    statut: StatutTicket = StatutTicket.ouvert
    priorite: PrioriteTicket = PrioriteTicket.normale
    auteur_id: int = Field(foreign_key="utilisateur.id")
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    perimetre_cible: Optional[str] = Field(default='["résidence"]')  # JSON: résidence|bat:{id}|parking|cave
    photos_urls: Optional[str] = None  # JSON array of photo URLs
    destinataire_syndic: bool = False
    destinataire_cs: bool = False
    saisi_pour_user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: datetime = Field(default_factory=datetime.utcnow)
    ferme_le: Optional[datetime] = None

    auteur: Optional[Utilisateur] = Relationship(back_populates="tickets", sa_relationship_kwargs={"foreign_keys": "[Ticket.auteur_id]"})
    saisi_pour: Optional[Utilisateur] = Relationship(sa_relationship_kwargs={"foreign_keys": "[Ticket.saisi_pour_user_id]"})
    lot: Optional[Lot] = Relationship(back_populates="tickets")
    messages: List["MessageTicket"] = Relationship(back_populates="ticket")
    evolutions: List["TicketEvolution"] = Relationship(back_populates="ticket")


class MessageTicket(SQLModel, table=True):
    __tablename__ = "message_ticket"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id")
    auteur_id: int = Field(foreign_key="utilisateur.id")
    contenu: str
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    interne: bool = False  # True = visible CS seulement

    ticket: Optional[Ticket] = Relationship(back_populates="messages")


class TicketEvolution(SQLModel, table=True):
    __tablename__ = "ticket_evolution"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id")
    # type : commentaire | etat | reponse
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)

    ticket: Optional[Ticket] = Relationship(back_populates="evolutions")
    auteur: Optional[Utilisateur] = Relationship()


# ──────────────────────────────────────────────
#  Publications / Actualités
# ──────────────────────────────────────────────

class Publication(SQLModel, table=True):
    __tablename__ = "publication"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    contenu: str
    perimetre: str = "résidence"  # résidence | bâtiment
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    epingle: bool = False
    urgente: bool = False
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    publiee_le: Optional[datetime] = None
    mis_a_jour_le: Optional[datetime] = None
    image_url: Optional[str] = None
    perimetre_cible: Optional[str] = Field(default='["résidence"]')  # JSON: résidence|bat:{id}|parking|cave|résidents
    public_cible: Optional[str] = Field(default='["résidents"]')     # JSON: résidents|locataires|copropriétaires
    # statut : en_cours | resolu | annule | None
    statut: Optional[str] = None
    statut_change_le: Optional[datetime] = None
    brouillon: bool = False
    archivee: bool = False
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False

    auteur: Optional[Utilisateur] = Relationship(back_populates="publications")
    evolutions: List["PublicationEvolution"] = Relationship(back_populates="publication")


class PublicationEvolution(SQLModel, table=True):
    __tablename__ = "publication_evolution"
    id: Optional[int] = Field(default=None, primary_key=True)
    publication_id: int = Field(foreign_key="publication.id")
    # type : commentaire | etat | correction
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)

    publication: Optional[Publication] = Relationship(back_populates="evolutions")
    auteur: Optional[Utilisateur] = Relationship()


# ──────────────────────────────────────────────
#  Documents
# ──────────────────────────────────────────────

class ProfilAccesDocument(SQLModel, table=True):
    __tablename__ = "profil_acces_document"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    libelle: str
    description: str = ""
    roles_autorises: str  # JSON array des statuts
    require_cs: bool = False
    actif: bool = True

    categories: List["CategorieDocument"] = Relationship(back_populates="profil_acces")


class CategorieDocument(SQLModel, table=True):
    __tablename__ = "categorie_document"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    libelle: str
    profil_acces_id: int = Field(foreign_key="profil_acces_document.id")
    perimetre_defaut: str = "résidence"
    surcharge_autorisee: bool = False
    actif: bool = True

    profil_acces: Optional[ProfilAccesDocument] = Relationship(back_populates="categories")
    documents: List["Document"] = Relationship(back_populates="categorie")


class Document(SQLModel, table=True):
    __tablename__ = "document"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    fichier_nom: str
    fichier_chemin: str
    taille_octets: Optional[int] = None
    mime_type: str = "application/octet-stream"
    categorie_id: Optional[int] = Field(default=None, foreign_key="categorie_document.id")
    contrat_id: Optional[int] = Field(default=None, foreign_key="contrat_entretien.id")
    profil_acces_override_id: Optional[int] = Field(default=None, foreign_key="profil_acces_document.id")
    perimetre: str = "résidence"
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")
    publie_par_id: int = Field(foreign_key="utilisateur.id")
    publie_le: datetime = Field(default_factory=datetime.utcnow)
    # Champs spécifiques aux CR d'AG
    annee: Optional[int] = None
    date_ag: Optional[date] = Field(default=None)
    batiments_ids_json: Optional[str] = None  # JSON array ex: "[1,2]" pour AG multi-bâtiments

    categorie: Optional[CategorieDocument] = Relationship(back_populates="documents")


# ──────────────────────────────────────────────
#  Règles & Recommandations de la résidence
# ──────────────────────────────────────────────

class RegleResidence(SQLModel, table=True):
    __tablename__ = "regle_residence"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    contenu: str = ""
    ordre: int = Field(default=0)
    cree_par_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    modifie_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Délégations aidant
# ──────────────────────────────────────────────

class Delegation(SQLModel, table=True):
    __tablename__ = "delegation"
    id: Optional[int] = Field(default=None, primary_key=True)
    mandant_id: int = Field(foreign_key="utilisateur.id")      # la personne aidée
    aidant_id: int = Field(foreign_key="utilisateur.id")        # le proche aidant
    statut: StatutDelegation = StatutDelegation.en_attente
    motif: str = ""                                              # raison de la délégation
    date_debut: date = Field(default_factory=date.today)
    date_fin: Optional[date] = None                              # null = pas de limite
    cree_par_id: int = Field(foreign_key="utilisateur.id")       # CS/admin qui a créé
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    revoque_le: Optional[datetime] = None
    revoque_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")


# ──────────────────────────────────────────────
#  Prestataires / Contrats
# ──────────────────────────────────────────────

class Prestataire(SQLModel, table=True):
    __tablename__ = "prestataire"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str
    specialite: str
    type_prestataire: TypePrestataire = TypePrestataire.ponctuel
    telephone: Optional[str] = None
    email: Optional[str] = None
    contacts_json: Optional[str] = None  # JSON: [{prenom, nom, fonction, email, telephone}]
    actif: bool = True

    contrats: List["ContratEntretien"] = Relationship(back_populates="prestataire")
    devis: List["DevisPrestataire"] = Relationship(back_populates="prestataire")


class ContratEntretien(SQLModel, table=True):
    __tablename__ = "contrat_entretien"
    id: Optional[int] = Field(default=None, primary_key=True)
    copropriete_id: int = Field(foreign_key="copropriete.id")
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    prestataire_id: int = Field(foreign_key="prestataire.id")

    type_equipement: TypeEquipement = TypeEquipement.autre
    libelle: str
    numero_contrat: Optional[str] = None
    date_debut: date = Field(default_factory=date.today)
    duree_initiale_valeur: Optional[int] = None
    duree_initiale_unite: Optional[str] = None  # "mois" ou "ans"
    frequence_type: Optional[str] = None  # "semaines", "mois", "fois_par_an"
    frequence_valeur: Optional[int] = None
    prochaine_visite: Optional[date] = None
    actif: bool = True
    notes: Optional[str] = None
    document_id: Optional[int] = Field(default=None, foreign_key="document.id")

    copropriete: Optional[Copropriete] = Relationship(back_populates="contrats_entretien")
    prestataire: Optional[Prestataire] = Relationship(back_populates="contrats")


class DevisPrestataire(SQLModel, table=True):
    __tablename__ = "devis_prestataire"
    id: Optional[int] = Field(default=None, primary_key=True)
    copropriete_id: int = Field(foreign_key="copropriete.id")
    prestataire_id: int = Field(foreign_key="prestataire.id")
    titre: str
    date_prestation: Optional[date] = None
    montant_estime: Optional[float] = None
    statut: StatutDevis = StatutDevis.en_attente
    frequence_type: Optional[str] = None   # "semaines", "mois", "fois_par_an"
    frequence_valeur: Optional[int] = None
    notes: Optional[str] = None
    perimetre: str = "résidence"
    fichiers_urls: Optional[str] = None  # JSON array of file URLs
    os_fichier_url: Optional[str] = None  # URL de l'ordre de service signé
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    actif: bool = True
    affichable: bool = Field(default=False)  # visible dans le dashboard (évènements récents)
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: Optional[datetime] = Field(default=None)

    prestataire: Optional[Prestataire] = Relationship(back_populates="devis")


class NotationPrestataire(SQLModel, table=True):
    """Notation d'un prestataire (1-5 étoiles) après une visite ou prestation ponctuelle."""
    __tablename__ = "notation_prestataire"
    id: Optional[int] = Field(default=None, primary_key=True)
    prestataire_id: int = Field(foreign_key="prestataire.id")
    note: int  # 1 à 5
    commentaire: Optional[str] = None
    devis_id: Optional[int] = Field(default=None, foreign_key="devis_prestataire.id")
    contrat_id: Optional[int] = Field(default=None, foreign_key="contrat_entretien.id")
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
#  Relevés compteurs
# ──────────────────────────────────────────────

class ReleveCompteur(SQLModel, table=True):
    __tablename__ = "releve_compteur"
    id: Optional[int] = Field(default=None, primary_key=True)
    type_compteur: str                          # "eau_general", …
    date_releve: date = Field(default_factory=date.today)
    index: Optional[int] = None                # index lu (None si non relevé / changement)
    note: Optional[str] = None                 # ex : "Changement compteur"
    photo_url: Optional[str] = None
    prestataire_id: Optional[int] = Field(default=None, foreign_key="prestataire.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    cree_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")


# ──────────────────────────────────────────────
#  Configuration des compteurs (consommations)
# ──────────────────────────────────────────────

class CompteurConfig(SQLModel, table=True):
    __tablename__ = "compteur_config"
    id: Optional[int] = Field(default=None, primary_key=True)
    type_compteur: str = Field(index=True)      # slug unique ex: "eau_general"
    label: str                                  # ex: "💧 Compteur EAU Général"
    prestataire_id: Optional[int] = Field(default=None, foreign_key="prestataire.id")
    actif: bool = True
    ordre: int = 0                              # for display order


# ──────────────────────────────────────────────
#  Templates email
# ──────────────────────────────────────────────

class ModeleEmail(SQLModel, table=True):
    __tablename__ = "modele_email"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    libelle: str
    sujet: str  # Jinja2
    corps_html: str  # Jinja2
    corps_texte: str = ""  # Fallback
    variables_disponibles: str = "[]"  # JSON
    desactivable: bool = True
    actif: bool = True
    modifie_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    modifie_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Sauvegardes
# ──────────────────────────────────────────────

class ConfigSauvegarde(SQLModel, table=True):
    __tablename__ = "config_sauvegarde"
    id: Optional[int] = Field(default=None, primary_key=True)
    active: bool = True
    frequence: FrequenceSauvegarde = FrequenceSauvegarde.quotidienne
    heure_execution: int = 3  # 0-23
    jour_semaine: int = 6     # 0=lun … 6=dim
    jour_mois: int = 1        # 1-28
    nb_versions_conservees: int = 7
    modifie_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    modifie_le: Optional[datetime] = None


class HistoriqueSauvegarde(SQLModel, table=True):
    __tablename__ = "historique_sauvegarde"
    id: Optional[int] = Field(default=None, primary_key=True)
    declenchee_par: str = "automatique"  # automatique | manuelle
    declenchee_par_user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    statut: StatutSauvegarde = StatutSauvegarde.en_cours
    fichier_nom: Optional[str] = None
    fichier_chemin: Optional[str] = None
    taille_octets: Optional[int] = None
    message_erreur: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    terminee_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Historique emails
# ──────────────────────────────────────────────

class HistoriqueEmail(SQLModel, table=True):
    __tablename__ = "historique_email"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)             # code du ModeleEmail
    destinataire: str                          # adresse email
    sujet: str = ""
    statut: str = "succes"                     # succes | erreur | ignore
    erreur: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow, index=True)


# ──────────────────────────────────────────────
#  Maintenance (cron)
# ──────────────────────────────────────────────

class HistoriqueMaintenance(SQLModel, table=True):
    __tablename__ = "historique_maintenance"
    id: Optional[int] = Field(default=None, primary_key=True)
    declenchee_par: str = "cron"               # cron | manuel
    statut: str = "succes"                     # succes | erreur
    tokens_supprimes: int = 0
    taille_db_octets: Optional[int] = None     # taille DB après VACUUM
    duree_secondes: Optional[int] = None
    erreur: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    terminee_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Télémétrie
# ──────────────────────────────────────────────

class TelemetryEvent(SQLModel, table=True):
    """Événement brut de télémétrie — conservé 30 jours puis agrégé."""
    __tablename__ = "telemetry_event"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    page: str = Field(index=True)          # ex: /actualites, /tickets
    action: str = "view"                    # view | click | submit
    detail: Optional[str] = None            # ex: bouton cliqué, id ticket
    cree_le: datetime = Field(default_factory=datetime.utcnow, index=True)


class TelemetryDaily(SQLModel, table=True):
    """Agrégation journalière — conservée 12 mois."""
    __tablename__ = "telemetry_daily"
    id: Optional[int] = Field(default=None, primary_key=True)
    jour: str = Field(index=True)           # YYYY-MM-DD
    page: str
    action: str = "view"
    utilisateurs_uniques: int = 0
    total: int = 0


class TelemetryMonthly(SQLModel, table=True):
    """Agrégation mensuelle — conservée 10 ans."""
    __tablename__ = "telemetry_monthly"
    id: Optional[int] = Field(default=None, primary_key=True)
    mois: str = Field(index=True)           # YYYY-MM
    page: str
    action: str = "view"
    utilisateurs_uniques: int = 0
    total: int = 0


class HistoriqueTelemetrie(SQLModel, table=True):
    """Historique des exécutions d'agrégation de la télémétrie."""
    __tablename__ = "historique_telemetrie"
    id: Optional[int] = Field(default=None, primary_key=True)
    declenchee_par: str = "cron"               # cron | manuelle
    statut: str = "en_cours"                   # en_cours | succes | erreur
    jours_agreges: int = 0
    mois_agreges: int = 0
    events_purges: int = 0
    daily_purges: int = 0
    monthly_purges: int = 0
    duree_secondes: Optional[float] = None
    erreur: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    terminee_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Notifications
# ──────────────────────────────────────────────

class Notification(SQLModel, table=True):
    __tablename__ = "notification"
    id: Optional[int] = Field(default=None, primary_key=True)
    destinataire_id: int = Field(foreign_key="utilisateur.id")
    type: str  # ticket_update | publication | vigik | urgence | system
    titre: str
    corps: str = ""
    lien: Optional[str] = None
    lue: bool = False
    urgente: bool = False
    cree_le: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
#  Vigik / Télécommandes (objets physiques)
# ──────────────────────────────────────────────

class StatutAcces(str, Enum):
    actif = "actif"
    suspendu = "suspendu"
    perdu = "perdu"


class Vigik(SQLModel, table=True):
    __tablename__ = "vigik"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str  # référence physique du badge
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")
    user_id: int = Field(foreign_key="utilisateur.id")
    statut: StatutAcces = StatutAcces.actif
    chez_locataire: bool = False  # True = en possession du locataire
    bail_id: Optional[int] = Field(default=None, foreign_key="location_bail.id")  # bail actif lors du transfert
    cree_le: datetime = Field(default_factory=datetime.utcnow)


class Telecommande(SQLModel, table=True):
    __tablename__ = "telecommande"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str  # référence physique
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")
    user_id: int = Field(foreign_key="utilisateur.id")
    statut: StatutAcces = StatutAcces.actif
    chez_locataire: bool = False  # True = la TC est en possession du locataire
    bail_id: Optional[int] = Field(default=None, foreign_key="location_bail.id")  # bail actif lors du transfert
    cree_le: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
#  Association M2M Vigik / Telecommande ↔ Utilisateur
#  (un badge peut être associé à plusieurs copropriétaires)
# ──────────────────────────────────────────────

class UserVigik(SQLModel, table=True):
    __tablename__ = "user_vigik"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    vigik_id: int = Field(foreign_key="vigik.id")


class UserTelecommande(SQLModel, table=True):
    __tablename__ = "user_telecommande"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="utilisateur.id")
    telecommande_id: int = Field(foreign_key="telecommande.id")


# ──────────────────────────────────────────────
#  Import télécommandes (staging depuis Excel)
# ──────────────────────────────────────────────

class StatutImport(str, Enum):
    en_attente         = "en_attente"          # aucun user matché
    proprietaire_lie   = "proprietaire_lie"    # proprio matché, locataire en attente
    resolu             = "resolu"              # TC créée, tout lié
    ignore             = "ignore"              # admin a choisi d'ignorer cette ligne


class TelecommandeImport(SQLModel, table=True):
    """Staging des télécommandes importées depuis l'Excel, en attente de résolution
    par l'admin au fur et à mesure des inscriptions des résidents."""
    __tablename__ = "telecommande_import"

    id: Optional[int] = Field(default=None, primary_key=True)

    # ── Données brutes issues de l'Excel ──────────────────────────────────
    nom_proprietaire: str            # colonne A
    nom_locataire: Optional[str] = None   # colonne B — None si vide
    reference: Optional[str] = None  # colonne C — None sur quelques lignes spéciales

    # ── Résolution (rempli par l'admin) ──────────────────────────────────
    statut: StatutImport = StatutImport.en_attente

    user_proprietaire_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    user_locataire_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")

    # Possession physique de la TC
    chez_locataire: bool = False           # TC en possession du locataire
    refuse_par_locataire: bool = False     # locataire a refusé → reste chez proprio

    # Lien vers la Telecommande créée lors de la résolution
    telecommande_id: Optional[int] = Field(default=None, foreign_key="telecommande.id")

    # ── Métadonnées ───────────────────────────────────────────────────────
    notes_admin: Optional[str] = None
    importe_le: datetime = Field(default_factory=datetime.utcnow)
    resolu_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Import vigiks (staging depuis Excel)
# ──────────────────────────────────────────────

class VigikImport(SQLModel, table=True):
    """Staging des vigiks importés depuis l'Excel, en attente de résolution
    par l'admin au fur et à mesure des inscriptions des résidents."""
    __tablename__ = "vigik_import"

    id: Optional[int] = Field(default=None, primary_key=True)

    # ── Données brutes issues de l'Excel ──────────────────────────────────
    batiment_raw: Optional[str] = None       # col A — numéro de bâtiment
    appartement_raw: Optional[str] = None    # col B — numéro d'appartement
    nom_proprietaire: str                    # col C
    nom_locataire: Optional[str] = None      # col D — None si vide
    code: Optional[str] = None              # col E — N° CLÉS

    # ── Résolution (rempli par l'admin) ──────────────────────────────────
    statut: StatutImport = StatutImport.en_attente

    user_proprietaire_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    user_locataire_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")

    # Possession physique du vigik
    chez_locataire: bool = False
    refuse_par_locataire: bool = False

    # Lien vers le Vigik créé lors de la résolution
    vigik_id: Optional[int] = Field(default=None, foreign_key="vigik.id")

    # ── Métadonnées ───────────────────────────────────────────────────────
    notes_admin: Optional[str] = None
    importe_le: datetime = Field(default_factory=datetime.utcnow)
    resolu_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Import lots (staging depuis Excel)
# ──────────────────────────────────────────────

class StatutLotImport(str, Enum):
    en_attente      = "en_attente"       # importé, rien de lié
    utilisateur_lie = "utilisateur_lie"  # occupant(s) identifié(s), lot pas encore trouvé
    lot_lie         = "lot_lie"          # lot_id trouvé/confirmé en base
    resolu          = "resolu"           # UserLot créé (lot + occupants confirmés)
    ignore          = "ignore"


class LotImport(SQLModel, table=True):
    """Staging des lots importés depuis l'Excel,
    en attente de liaison avec les utilisateurs de l'application."""
    __tablename__ = "lot_import"

    id: Optional[int] = Field(default=None, primary_key=True)

    # ── Données brutes de l'Excel ─────────────────────────────────────────
    batiment_id: Optional[int] = None          # col A — None pour les parkings
    numero: str                                # col B
    type_raw: str                              # col C (AP, ST, T2, CA, PS…)
    etage_raw: Optional[str] = None            # col D
    no_coproprietaire: Optional[str] = None    # col F
    nom_coproprietaire: Optional[str] = None   # col G

    # ── Résolution par l'admin ────────────────────────────────────────────
    statut: StatutLotImport = StatutLotImport.en_attente

    lot_id: Optional[int] = Field(default=None, foreign_key="lot.id")

    # JSON array de {user_id, type_lien} — plusieurs occupants possibles
    # ex. [{"user_id": 12, "type_lien": "propriétaire"},
    #       {"user_id": 15, "type_lien": "locataire"}]
    utilisateurs_json: str = Field(default="[]")

    notes_admin: Optional[str] = None
    importe_le: datetime = Field(default_factory=datetime.utcnow)
    resolu_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Calendrier de la résidence
# ──────────────────────────────────────────────

class TypeEvenement(str, Enum):
    travaux = "travaux"
    coupure = "coupure"
    ag = "ag"
    maintenance = "maintenance"
    maintenance_recurrente = "maintenance_recurrente"
    autre = "autre"


class StatutKanban(str, Enum):
    ag = "ag"
    cs = "cs"
    syndic = "syndic"
    fournisseur = "fournisseur"
    termine = "termine"
    annule = "annule"


class Evenement(SQLModel, table=True):
    __tablename__ = "evenement"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    description: Optional[str] = None
    type: TypeEvenement = TypeEvenement.autre
    lieu: Optional[str] = None
    debut: datetime
    fin: Optional[datetime] = None
    perimetre: str = "résidence"  # résidence | bâtiment
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: Optional[datetime] = None
    archivee: bool = False
    statut_kanban: Optional[str] = Field(default=None)  # ag|cs|syndic|fournisseur|termine|annule
    prestataire_id: Optional[int] = Field(default=None, foreign_key="prestataire.id")
    frequence_type: Optional[str] = Field(default=None)   # "semaines", "mois", "fois_par_an"
    frequence_valeur: Optional[int] = Field(default=None)
    affichable: bool = Field(default=False)  # visible dans le dashboard (évènements récents)
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False


# ──────────────────────────────────────────────
#  Sondages
# ──────────────────────────────────────────────

class Sondage(SQLModel, table=True):
    __tablename__ = "sondage"
    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    resultats_publics: bool = True  # visibles avant clôture
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    # Ciblage : None/vide = tous
    profils_autorises: Optional[str] = Field(default=None)   # CSV de StatutUtilisateur
    batiments_ids: Optional[str] = Field(default=None)       # CSV d'ids de Batiment
    cloture_forcee: bool = Field(default=False)
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False

    options: List["OptionSondage"] = Relationship(back_populates="sondage")
    votes: List["VoteSondage"] = Relationship(back_populates="sondage")


class OptionSondage(SQLModel, table=True):
    __tablename__ = "option_sondage"
    id: Optional[int] = Field(default=None, primary_key=True)
    sondage_id: int = Field(foreign_key="sondage.id")
    libelle: str
    ordre: int = 0
    champ_libre: bool = Field(default=False)

    sondage: Optional[Sondage] = Relationship(back_populates="options")
    votes: List["VoteSondage"] = Relationship(back_populates="option")


class VoteSondage(SQLModel, table=True):
    __tablename__ = "vote_sondage"
    id: Optional[int] = Field(default=None, primary_key=True)
    sondage_id: int = Field(foreign_key="sondage.id")
    option_id: int = Field(foreign_key="option_sondage.id")
    user_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    reponse_libre: Optional[str] = Field(default=None)

    sondage: Optional[Sondage] = Relationship(back_populates="votes")
    option: Optional[OptionSondage] = Relationship(back_populates="votes")


# ──────────────────────────────────────────────
#  Petites annonces
# ──────────────────────────────────────────────

class TypeAnnonce(str, Enum):
    vente = "vente"
    don = "don"
    recherche = "recherche"


class CategorieAnnonce(str, Enum):
    appartement = "appartement"
    parking_cave = "parking_cave"
    mobilier = "mobilier"
    electromenager = "electromenager"
    high_tech = "high_tech"
    vehicule = "vehicule"
    vetements = "vetements"
    services = "services"
    divers = "divers"


class StatutAnnonce(str, Enum):
    disponible = "disponible"
    reserve = "reserve"
    vendu = "vendu"
    archive = "archive"


class PetiteAnnonce(SQLModel, table=True):
    __tablename__ = "petite_annonce"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    description: str  # rich-text HTML
    type_annonce: TypeAnnonce = TypeAnnonce.vente
    categorie: CategorieAnnonce = CategorieAnnonce.divers
    prix: Optional[float] = None
    negotiable: bool = False
    photos_json: str = Field(default="[]")  # JSON array of up to 5 URLs
    statut: StatutAnnonce = StatutAnnonce.disponible
    contact_visible: bool = True  # autoriser affichage email/prénom-nom
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Annuaire CS & Syndic
# ──────────────────────────────────────────────

class GenreCivilite(str, Enum):
    mr   = "Mr"
    mme  = "Mme"
    mlle = "Mlle"


class AgCsInfo(SQLModel, table=True):
    """Informations AG du Conseil Syndical. Un seul enregistrement (upsert)."""
    __tablename__ = "ag_cs_info"
    id:       Optional[int]  = Field(default=None, primary_key=True)
    ag_annee: Optional[int]  = None
    ag_date:  Optional[date] = None


class MembreCS(SQLModel, table=True):
    """Membre du Conseil Syndical (indépendant des comptes Utilisateur)."""
    __tablename__ = "membre_cs"
    id:          Optional[int]          = Field(default=None, primary_key=True)
    genre:       GenreCivilite
    prenom:      str
    nom:         str
    batiment_id: Optional[int]          = Field(default=None, foreign_key="batiment.id")
    etage:       Optional[int]          = None
    est_gestionnaire_site: bool         = False
    est_president: bool                 = False
    ordre:       int                    = 0
    user_id:     Optional[int]          = Field(default=None, foreign_key="utilisateur.id")


class SyndicInfo(SQLModel, table=True):
    """Informations du syndic. Un seul enregistrement (upsert)."""
    __tablename__ = "syndic_info"
    id:         Optional[int] = Field(default=None, primary_key=True)
    nom_syndic: str           = ""
    adresse:    str           = ""
    site_web:   Optional[str] = None


class MembreSyndic(SQLModel, table=True):
    """Membre du syndic (indépendant des comptes Utilisateur)."""
    __tablename__ = "membre_syndic"
    id:            Optional[int]    = Field(default=None, primary_key=True)
    genre:         GenreCivilite
    prenom:        str
    nom:           str
    fonction:      Optional[str]    = None
    email:         Optional[str]    = None
    telephone:     Optional[str]    = None   # CSV comma-separated, même pattern que Prestataire
    est_principal: bool             = False
    ordre:         int              = 0
    user_id:       Optional[int]    = Field(default=None, foreign_key="utilisateur.id")


class CommentaireSondage(SQLModel, table=True):
    __tablename__ = "commentaire_sondage"
    id: Optional[int] = Field(default=None, primary_key=True)
    sondage_id: int = Field(foreign_key="sondage.id")
    auteur_id: int = Field(foreign_key="utilisateur.id")
    contenu: str
    cree_le: datetime = Field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
#  Diagnostics et Contrôles Réglementaires
# ──────────────────────────────────────────────

class DiagnosticType(SQLModel, table=True):
    __tablename__ = "diagnostic_type"
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True)
    nom: str
    texte_legislatif: str
    frequence: Optional[str] = None  # ex: "10 ans", "3 ans", "Permanent", None
    ordre: int = 0
    actif: bool = True
    non_applicable: bool = False

    rapports: List["DiagnosticRapport"] = Relationship(back_populates="type_diagnostic")


class DiagnosticRapport(SQLModel, table=True):
    __tablename__ = "diagnostic_rapport"
    id: Optional[int] = Field(default=None, primary_key=True)
    diagnostic_type_id: int = Field(foreign_key="diagnostic_type.id")
    titre: str
    date_rapport: Optional[date] = None
    fichier_nom: str
    fichier_chemin: str
    taille_octets: Optional[int] = None
    mime_type: str = "application/octet-stream"
    synthese: Optional[str] = None  # synthèse des conclusions du rapport
    publie_par_id: int = Field(foreign_key="utilisateur.id")
    publie_le: datetime = Field(default_factory=datetime.utcnow)

    type_diagnostic: Optional[DiagnosticType] = Relationship(back_populates="rapports")


# ──────────────────────────────────────────────
#  Boîte à idées
# ──────────────────────────────────────────────

class Idee(SQLModel, table=True):
    __tablename__ = "idee"
    id: Optional[int] = Field(default=None, primary_key=True)
    titre: str
    description: str
    auteur_id: int = Field(foreign_key="utilisateur.id")
    statut: str = "ouverte"  # ouverte | retenue | rejetee | realisee
    cree_le: datetime = Field(default_factory=datetime.utcnow)

    votes: List["VoteIdee"] = Relationship(back_populates="idee")


class VoteIdee(SQLModel, table=True):
    __tablename__ = "vote_idee"
    id: Optional[int] = Field(default=None, primary_key=True)
    idee_id: int = Field(foreign_key="idee.id")
    user_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)

    idee: Optional[Idee] = Relationship(back_populates="votes")


# ──────────────────────────────────────────────
#  Location (gestion bailleur → locataire)
# ──────────────────────────────────────────────

class StatutBail(str, Enum):
    actif   = "actif"    # locataire en place
    termine = "termine"  # locataire parti
    en_cours_sortie = "en_cours_sortie"  # préavis en cours


class StatutObjet(str, Enum):
    en_possession = "en_possession"  # remis, pas encore rendu
    rendu         = "rendu"          # rendu à la sortie
    perdu         = "perdu"          # déclaré perdu
    non_remis     = "non_remis"      # prévu mais pas encore remis


class TypeObjet(str, Enum):
    cle           = "cle"
    telecommande  = "telecommande"
    vigik         = "vigik"
    autre         = "autre"


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

    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: datetime = Field(default_factory=datetime.utcnow)

    objets: List["RemiseObjet"] = Relationship(back_populates="bail")


class RemiseObjet(SQLModel, table=True):
    """Objet physique remis (ou à remettre) au locataire dans le cadre d'un bail."""
    __tablename__ = "remise_objet"

    id: Optional[int] = Field(default=None, primary_key=True)
    bail_id: int = Field(foreign_key="location_bail.id", index=True)
    type: TypeObjet = TypeObjet.autre
    libelle: str            # ex. "Clé Porte palière", "Télécommande Parking"
    quantite: int = 1
    reference: Optional[str] = None  # ex. "TC-042", "VGK-007"
    statut: StatutObjet = StatutObjet.en_possession
    remis_le: Optional[date] = None
    rendu_le: Optional[date] = None
    notes: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)

    bail: Optional[LocationBail] = Relationship(back_populates="objets")


# ──────────────────────────────────────────────
#  Demandes de modification de profil
# ──────────────────────────────────────────────

class StatutDemandeProfil(str, Enum):
    en_attente = "en_attente"
    approuvee = "approuvee"
    rejetee = "rejetee"


class DemandeModificationProfil(SQLModel, table=True):
    """Demande de modification du type de résident ou du bâtiment, soumise à validation CS."""
    __tablename__ = "demande_modification_profil"

    id: Optional[int] = Field(default=None, primary_key=True)
    utilisateur_id: int = Field(foreign_key="utilisateur.id", index=True)
    statut_souhaite: Optional[str] = None      # valeur de StatutUtilisateur souhaitée
    batiment_id_souhaite: Optional[int] = Field(default=None, foreign_key="batiment.id")
    motif: Optional[str] = None                # justification libre de l'utilisateur
    statut_demande: StatutDemandeProfil = StatutDemandeProfil.en_attente
    motif_refus: Optional[str] = None
    traite_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    traite_le: Optional[datetime] = None


# ──────────────────────────────────────────────
#  Configuration site (persistance multi-appareils)
# ──────────────────────────────────────────────

class ConfigSite(SQLModel, table=True):
    """Paramètres de configuration sauvegardés par l'admin (titre, descriptif, nom du site…).
    Stockés en base pour être visibles de tous les appareils."""
    __tablename__ = "config_site"
    cle: str = Field(primary_key=True)
    valeur: str


# ──────────────────────────────────────────────
#  Messages WhatsApp planifiés
# ──────────────────────────────────────────────

class WhatsAppScheduled(SQLModel, table=True):
    __tablename__ = "whatsapp_scheduled"
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str                    # ex. "Encombrants Bd Hostachy"
    message: str                  # texte du message
    cron_rule: str                # ex. "3eme_samedi" ou "4eme_samedi"
    enabled: bool = True
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: datetime = Field(default_factory=datetime.utcnow)


class WhatsAppLog(SQLModel, table=True):
    __tablename__ = "whatsapp_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    scheduled_id: Optional[int] = Field(default=None, foreign_key="whatsapp_scheduled.id")
    label: str = ""
    message: str
    statut: str = "envoyé"        # envoyé | échec
    erreur: Optional[str] = None
    envoye_le: datetime = Field(default_factory=datetime.utcnow)
