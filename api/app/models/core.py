"""
Modèles SQLModel — version 0.1
Correspond au modèle de données défini dans specs/architecture/modele-donnees.md
"""
from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel

#  Réexportation : `Copropriete`, `Batiment`, `Lot` et `TypeLot` vivent dans
#  `copropriete.py` depuis le 13/08/2026 (modularité, rang 1). Ils restent
#  importables ici pour ne pas avoir à toucher sept modules appelants — dont
#  `auth.py`, que sa taille empêche de recevoir une ligne d'import de plus.
from app.models.copropriete import (
    Batiment as Batiment,
    Copropriete as Copropriete,
    Lot as Lot,
    TypeLot as TypeLot,
)

#  Réexportation : les rôles, les statuts et la hiérarchie qui les départage
#  vivent dans `roles.py` depuis le 15/09/2026 (modularité, rang 1). Ce
#  fichier était à 924 lignes et ne pouvait plus grossir pour recevoir la
#  règle — qui, elle, était écrite deux fois trente lignes plus bas. Ils
#  restent importables ici : aucun des appelants ne change, et SQLModel
#  continue de connaître les énumérations.
from app.models.roles import (
    PRIORITE_ROLE as PRIORITE_ROLE,
    RoleUtilisateur as RoleUtilisateur,
    StatutUtilisateur as StatutUtilisateur,
    rang_role as rang_role,
    role_principal,
)
from app.models.acces import (
    StatutAcces as StatutAcces,
    StatutImport as StatutImport,
    Telecommande as Telecommande,
    TelecommandeImport as TelecommandeImport,
    UserTelecommande as UserTelecommande,
    UserVigik as UserVigik,
    Vigik as Vigik,
    VigikImport as VigikImport,
)
from app.utils.assiste_ia import AssisteIAMixin
from app.utils.saisi_pour import SaisiPourMixin
from app.models.evolution import EvolutionMixin


# ──────────────────────────────────────────────
#  Enums
# ──────────────────────────────────────────────


class StatutDelegation(str, Enum):
    en_attente = "en_attente"       # créée par le CS, en attente d'acceptation
    active = "active"               # acceptée par l'aidant
    revoquee = "revoquee"           # révoquée par le mandant ou le CS
    expiree = "expiree"             # date de fin dépassée



class TypeLien(str, Enum):
    propriétaire = "propriétaire"   # copropriétaire résident (occupe le lot)
    bailleur     = "bailleur"       # copropriétaire non-résident (loue le lot)
    locataire    = "locataire"      # locataire d'un bailleur
    mandataire   = "mandataire"     # mandataire de gestion (se substitue au bailleur)


#  Le vocabulaire du ticket — états, catégories, priorités — vit dans
#  `tickets.py` depuis le 17/08/2026 (modularité, rang 1) : `core.py` ne
#  pouvait plus grossir pour recevoir #415. Ré-exporté ici, donc aucun des
#  dix-huit appelants ne change, et les valeurs restent connues de SQLModel.
from app.models.tickets import (  # noqa: E402
    STATUTS_TICKET_ACTIFS as STATUTS_TICKET_ACTIFS,
    STATUTS_TICKET_CLOS as STATUTS_TICKET_CLOS,
    STATUTS_TICKET_HISTORIQUES as STATUTS_TICKET_HISTORIQUES,
    CategorieTicket as CategorieTicket,
    PrioriteTicket as PrioriteTicket,
    StatutTicket as StatutTicket,
)


#  `TypePrestataire` et `TypeEquipement` sont parties avec leurs modèles dans
#  `models/prestataires.py` ; elles sont réimportées plus bas, avec eux.
#  `StatutDevis` a suivi la prestation ponctuelle (#603) et n'existe plus.

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
    actif: bool = Field(default=False)  # False = pas (ou plus) autorisé à se connecter
    #  Quand l'administration a TRANCHÉ sur ce compte — validation, refus ou
    #  désactivation. `actif == False` ne suffisait pas à dire « en attente » :
    #  un compte refusé et un compte désactivé volontairement portent le même
    #  drapeau, et gonflaient donc le décompte des validations indéfiniment
    #  (#399). Le refus ne changeait d'ailleurs AUCUN état — le compte refusé
    #  revenait à chaque chargement de l'écran. Ne jamais lire ce champ à la
    #  main : `app/utils/comptes.py` porte la question et la réponse.
    decision_compte_le: Optional[datetime] = Field(default=None)
    email_verifie: bool = Field(default=False)  # False = email non confirmé
    onboarding_complete: bool = False
    onboarding_etape: int = 0  # 0-4
    photo_url: Optional[str] = None
    #  Où la personne HABITE — facultatif, et distinct de `Lot.etage`, qui
    #  décrit un BIEN (un bailleur a un lot au 4ᵉ et habite ailleurs).
    #  Le pourquoi et la prudence RGPD : migration 0178.
    etage: Optional[int] = None
    societe: Optional[str] = None
    fonction: Optional[str] = None
    consentement_rgpd: bool = False
    opt_out_telemetrie: bool = Field(default=False)
    communaute_interdit: bool = Field(default=False)  # ban permanent (2e infraction)
    communaute_ban_count: int = Field(default=0)  # 0=jamais banni, 1=1er ban, 2+=permanent
    communaute_ban_jusqu_au: Optional[datetime] = Field(default=None)  # fin du ban temporaire
    #  Deux clés depuis le 14/08/2026 (#339) — `utils/preferences_mail.py` fait foi
    #  et réapplique ces défauts à la lecture, quel que soit l'état du champ.
    preferences_notifications: str = Field(default='{"mon_batiment_mail": true, "autres_batiments_mail": false}')
    #  Préférence d'AFFICHAGE, jamais un droit : ne voir que ses bâtiments (#339).
    #  Elle ne protège rien — la confidentialité reste portée par `public_cible`
    #  et les profils d'accès aux documents, que ce lot ne touche pas.
    restreindre_a_mes_batiments: bool = Field(default=False)
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
        self.role = role_principal(current, defaut=rv) or self.role

    def retirer_role(self, role: "RoleUtilisateur") -> None:
        """Retire un rôle. Garde au minimum 'résident'."""
        rv = role.value if hasattr(role, "value") else str(role)
        current = [r for r in self.roles if r != rv]
        if not current:
            current = [RoleUtilisateur.résident.value]
        self.roles_json = ",".join(current)
        self.role = (
            role_principal(current, defaut=RoleUtilisateur.résident.value)
            or self.role
        )
    tickets: List["Ticket"] = Relationship(back_populates="auteur", sa_relationship_kwargs={"foreign_keys": "[Ticket.auteur_id]"})
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


# ──────────────────────────────────────────────
#  Files de validation (accès, demandes de profil)
# ──────────────────────────────────────────────
#  Les tables vivent dans `models/validations.py` depuis le 17/08/2026
#  (modularité, rang 1). Ré-exportées ici : les imports existants ne bougent
#  pas, et les modèles restent enregistrés auprès de SQLModel.
from app.models.validations import (  # noqa: E402,F401
    CommandeAcces as CommandeAcces,
    DemandeModificationProfil as DemandeModificationProfil,
    StatutCommande as StatutCommande,
    StatutDemandeProfil as StatutDemandeProfil,
)


# ──────────────────────────────────────────────
#  Tickets
# ──────────────────────────────────────────────

class Ticket(SaisiPourMixin, AssisteIAMixin, table=True):
    __tablename__ = "ticket"
    id: Optional[int] = Field(default=None, primary_key=True)
    numero: str = Field(unique=True, index=True)
    #  D'où vient cette affaire, quand elle est née d'une actualité promue
    #  (#1094). Pas de `foreign_key` : la publication référencée est SUPPRIMÉE
    #  par la promotion même. Le pourquoi — et ce que cette trace empêche — est
    #  dans `routers/publications/promotion.py`, qui est le seul à l'écrire.
    promu_depuis_publication_id: Optional[int] = Field(default=None, index=True)
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
    # Pièces jointes non-images (PDF, bureautique). Même convention que
    # TicketEvolution.fichiers_urls : un seul nom pour la notion « fichier joint ».
    fichiers_urls: str = "[]"  # JSON array d'URLs de fichiers joints
    destinataire_syndic: bool = False
    destinataire_cs: bool = False
    #  🔴 FK redéclarée : le mixin ne la porte pas (cf. `utils/saisi_pour`).
    saisi_pour_user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    non_relancable: bool = False
    #  -- Section « Quand » (#1092) ----------------------------------
    #  `debut`/`fin` disent QUAND ÇA SE PASSE et alimentent le calendrier.
    #  `echeance` (« avant quand c'est attendu ») a été RETIRÉE le 23/09/2026
    #  (migration 0206) : ôtée du formulaire le 21/09 — la relance mensuelle
    #  couvre le besoin —, elle n'était plus ni saisie ni lue.
    #  Noms alignés sur `Evenement.debut`/`fin` : le lot qui fera disparaître
    #  l'entité y recopiera ses lignes littéralement.
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    non_relancable_motif: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: datetime = Field(default_factory=datetime.utcnow)
    ferme_le: Optional[datetime] = None
    #  Adresse de réponse `tickets+<jeton>@…` (#703) : tiré au sort, jamais dérivé
    #  de l'id — il voyage dans les carnets d'adresses de toute la chaîne.
    jeton_courriel: Optional[str] = Field(default=None, index=True)
    #  Refermé sur son auteur et le CS (#710). Défaut `False`, comme
    #  `Publication.confidentiel` — voir la migration 0166 pour le pourquoi.
    confidentiel: bool = False
    #  📌 Épinglé (05/09/2026) ; ce que chaque option écrit : migration 0175.
    epingle: bool = False
    #  Paraît-il au kanban ? SI, jamais OÙ — `utils/kanban_tickets.py` (#833).
    suivi_kanban: bool = False
    #  Rapatriées de `Publication` (#1091, migration 0207) : le public visé
    #  (JSON), l'Accès « Réservé au périmètre » (#1096), l'archivage manuel.
    public_cible: Optional[str] = None
    reserve_perimetre: bool = False
    archive_manuel: bool = False

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
    fichiers_urls: str = "[]"  # JSON array d'URLs de fichiers joints

    ticket: Optional[Ticket] = Relationship(back_populates="messages")


class TicketEvolution(EvolutionMixin, table=True):
    __tablename__ = "ticket_evolution"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: int = Field(foreign_key="ticket.id")
    # type : commentaire | etat | reponse
    #  Les sept champs communs — `type`, `contenu`, les deux statuts,
    #  l'auteur, la date et les pièces jointes — viennent d'`EvolutionMixin`.
    #  Le périmètre que CETTE entrée déclare — `None` quand elle n'en parle pas,
    #  ce qui est le cas de l'immense majorité des commentaires : une évolution
    #  n'a pas de périmètre, elle en déclare un (migration 0154, #497).
    #  Même forme JSON que partout ailleurs : `["résidence"]`, `["bat:1","cave"]`.
    perimetre_cible: Optional[str] = None

    ticket: Optional[Ticket] = Relationship(back_populates="evolutions")
    auteur: Optional[Utilisateur] = Relationship()


# ──────────────────────────────────────────────
#  Publications / Actualités
# ──────────────────────────────────────────────

class Publication(SaisiPourMixin, AssisteIAMixin, table=True):
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
    #  -- Section « Quand » (#1092) ----------------------------------
    #  Une actualité datée — « Coupure d'eau jeudi 9h-12h » — paraît au
    #  calendrier sans qu'il faille en faire un troisième objet. Pas
    #  d'échéance ici : une actualité ne se suit pas, et une colonne que rien
    #  ne consomme ouvrirait un champ d'écran sans effet (cadre #430).
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    mis_a_jour_le: Optional[datetime] = None
    photos_urls: Optional[str] = None  # JSON array — même convention que Ticket/Evenement
    perimetre_cible: Optional[str] = Field(default='["résidence"]')  # JSON: résidence|bat:{id}|parking|cave|résidents
    public_cible: Optional[str] = Field(default='["résidents"]')     # JSON: résidents|locataires|copropriétaires
    # statut : publie (défaut, hors workflow) | en_cours | resolu | annule
    statut: Optional[str] = "publie"
    statut_change_le: Optional[datetime] = None
    brouillon: bool = False
    archivee: bool = False
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False
    annonce_hall: bool = False  # génère une affiche de hall à la publication
    #  Confidentiel : le périmètre redevient RESTRICTIF pour cette publication-là.
    #  Depuis #339, une actualité ciblée sur un bâtiment reste lisible de toute la
    #  copropriété ; ce drapeau rend la lecture au seul périmètre visé. Il ne fait
    #  que restreindre — il se combine en ET avec `public_cible` (cf. #347).
    confidentiel: bool = False

    auteur: Optional[Utilisateur] = Relationship(back_populates="publications")
    evolutions: List["PublicationEvolution"] = Relationship(back_populates="publication")

    @property
    def perime_le(self):
        """La date où cette actualité cesse d'être utile — **dérivée** (#1093).

        Elle ne se SAISIT pas : arbitré à l'écran le 22/09/2026, *« cette date
        est à enlever, elle est calculée par l'appli »*. Ce qui n'a pas de date
        d'événement ne périme pas, et n'en a pas besoin : l'archivage à trente
        jours couvre déjà ce cas pour les sept objets du site.

        Elle APPELLE la règle, elle ne la redérive pas : `utils/archivage`
        tranche pour le fil, le calendrier, les archives et cet objet. C'est
        la même discipline que `est_moderateur` et `estPerimetreParDefaut`.

        ⚠️ Une propriété et non une colonne : rien ne se stocke, donc rien ne
        périme en silence après un report d'événement. `PublicationRead` la lit
        par `from_attributes`.
        """
        from app.utils.archivage import perime_le  # import local : évite un cycle

        return perime_le(self)


class PublicationEvolution(EvolutionMixin, table=True):
    __tablename__ = "publication_evolution"
    id: Optional[int] = Field(default=None, primary_key=True)
    publication_id: int = Field(foreign_key="publication.id")
    # type : commentaire | etat — une correction est un `commentaire` préfixé « Correction : » (#433)
    #  Les sept champs communs — `type`, `contenu`, les deux statuts,
    #  l'auteur, la date et les pièces jointes — viennent d'`EvolutionMixin`.

    publication: Optional[Publication] = Relationship(back_populates="evolutions")
    auteur: Optional[Utilisateur] = Relationship()


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
#  Les quatre modèles vivent dans `models/prestataires.py` depuis le
#  20/08/2026 (#490). L'import n'est PAS décoratif : c'est lui qui enregistre
#  les tables auprès de SQLModel avant `create_all`.
from app.models.prestataires import (  # noqa: E402,F401
    ContratEntretien as ContratEntretien,
    NotationPrestataire as NotationPrestataire,
    Prestataire as Prestataire,
    TypeEquipement as TypeEquipement,
    TypePrestataire as TypePrestataire,
)

# ──────────────────────────────────────────────
#  Relevés compteurs
# ──────────────────────────────────────────────
#  Compteurs — relevés et configuration
# ──────────────────────────────────────────────
#  Les tables vivent dans `models/compteurs.py` depuis le 21/09/2026
#  (modularité, rang 1) : ce fichier était à 831 lignes et le contrôle a refusé
#  qu'il grossisse d'une colonne. Même motif qu'`evenement` (19/08) et
#  `exploitation` (20/09) — ré-exportées, donc les imports existants ne bougent
#  pas et les modèles restent enregistrés auprès de SQLModel.
#
#  Ces deux-là parce qu'elles ne portent AUCUNE `Relationship` : l'extraction
#  ne pouvait rien casser, et c'est ce qui l'a désignée plutôt qu'une autre au
#  milieu d'un lot qui parlait d'autre chose.
from app.models.compteurs import (  # noqa: E402,F401
    CompteurConfig as CompteurConfig,
    ReleveCompteur as ReleveCompteur,
)


# ──────────────────────────────────────────────
#  Templates email
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

# ──────────────────────────────────────────────
#  Calendrier
# ──────────────────────────────────────────────
#  Les tables vivent dans `models/evenement.py` depuis le 19/08/2026
#  (modularité, rang 1) — le module ne portait jusque-là que l'HISTORIQUE d'un
#  événement, pendant que l'événement lui-même restait ici : un module nommé
#  d'après une entité qui ne la contient pas. Ré-exportées : les imports
#  existants ne bougent pas, et les modèles restent enregistrés auprès de
#  SQLModel.
from app.models.evenement import (  # noqa: E402,F401
    Evenement as Evenement,
    StatutKanban as StatutKanban,
    TypeEvenement as TypeEvenement,
)


# ──────────────────────────────────────────────
#  Communauté (sondages, petites annonces, boîte à idées)
# ──────────────────────────────────────────────
#  Les tables vivent dans `models/communaute.py` depuis le 16/08/2026
#  (modularité, rang 1). Ré-exportées ici : les imports existants ne bougent
#  pas, et les modèles restent enregistrés auprès de SQLModel.
from app.models.communaute import (  # noqa: E402,F401
    CategorieAnnonce as CategorieAnnonce,
    CommentaireSondage as CommentaireSondage,
    FluxMasque as FluxMasque,
    Idee as Idee,
    OptionSondage as OptionSondage,
    PetiteAnnonce as PetiteAnnonce,
    ReponseCommunaute as ReponseCommunaute,
    Signalement as Signalement,
    Sondage as Sondage,
    StatutAnnonce as StatutAnnonce,
    TypeAnnonce as TypeAnnonce,
    VoteIdee as VoteIdee,
    VoteSondage as VoteSondage,
)


# ────────────────────────────────────────────
#  Annuaire CS & Syndic
# ────────────────────────────────────────────
#  Les quatre tables vivent dans `models/gouvernance.py` depuis le 22/09/2026
#  (modularité). Ré-exportées ici : les imports existants ne bougent pas, et la
#  table reste enregistrée auprès de SQLModel.
from app.models.gouvernance import (  # noqa: E402
    AgCsInfo as AgCsInfo,
    GenreCivilite as GenreCivilite,
    MembreCS as MembreCS,
    MembreSyndic as MembreSyndic,
    SyndicInfo as SyndicInfo,
)


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
#  Annonces Hall (Espace CS)
# ──────────────────────────────────────────────
#  La table vit dans `models/annonce_hall.py` depuis le 15/08/2026 (modularité).
#  Ré-exportée ici : les imports existants ne bougent pas.
from app.models.annonce_hall import AnnonceHall  # noqa: E402,F401


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


#  `StatutDemandeProfil` et `DemandeModificationProfil` sont montés plus haut,
#  avec `CommandeAcces` : les deux files vivaient à 900 lignes l'une de l'autre
#  alors qu'elles sont la même notion (cf. `models/validations.py`).


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
#  Messages WhatsApp planifiés — extraits le 05/09/2026 dans `models/whatsapp.py`
#  (modularité, rang 1). Ré-exportés ici : aucun appelant n'a changé.
# ──────────────────────────────────────────────
from app.models.whatsapp import (  # noqa: E402,F401
    WhatsAppLog as WhatsAppLog,
    WhatsAppScheduled as WhatsAppScheduled,
)

#  Réexportation : la bibliothèque documentaire vit dans `documents.py` depuis le
#  27/08/2026 (modularité, rang 1). Ces trois classes restent importables ici —
#  une vingtaine de modules écrivent `from app.models.core import Document`, et un
#  découpage qui casse ses importateurs n'est pas un découpage.
from app.models.documents import (
    CategorieDocument as CategorieDocument,
    Document as Document,
    ProfilAccesDocument as ProfilAccesDocument,
)


# ──────────────────────────────────────────────
#  Règles & Recommandations de la résidence
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
#  Sauvegardes
# ──────────────────────────────────────────────
#  Les deux tables vivent dans `models/sauvegarde.py` depuis le 14/08/2026
#  (modularité). Ré-exportées ici : les imports existants ne bougent pas.
from app.models.sauvegarde import (  # noqa: E402,F401
    ConfigSauvegarde,
    FrequenceSauvegarde,
    HistoriqueSauvegarde,
    StatutSauvegarde,
)
# ──────────────────────────────────────────────────────────────────────────
#  Jetons d'authentification — extraits dans `models/jetons.py` (#833).
#
#  ⚠️ Réimportés ici pour la même raison que la télémétrie : c'est CET import
#  qui enregistre les tables dans les métadonnées SQLModel.
# ──────────────────────────────────────────────────────────────────────────
from app.models.jetons import (  # noqa: E402,F401
    EmailVerificationToken, PasswordResetToken, RefreshToken,
)
# ──────────────────────────────────────────────────────────────────────────
#  Télémétrie — extraite dans `models/telemetrie.py` (plafond de modularité).
#  Réimportée ici : `from app.models.core import TelemetryEvent` reste valide,
#  et c'est cet import qui enregistre les tables dans les métadonnées SQLModel.
# ──────────────────────────────────────────────────────────────────────────
from app.models.telemetrie import (  # noqa: E402,F401
    TelemetryEvent, TelemetryDaily, TelemetryMonthly, HistoriqueTelemetrie,
)

#  ── L'EXPLOITATION vit dans `models/exploitation.py` (20/09/2026, #1092) ──
#
#  Courriels et maintenance sortis d'ici au titre du découpage au fil de l'eau.
#  Le ré-export garde importables les appelants qui écrivent
#  `from app.models.core import ModeleEmail` — même motif que les documents.
from app.models.exploitation import (  # noqa: E402
    HistoriqueEmail as HistoriqueEmail,
    HistoriqueMaintenance as HistoriqueMaintenance,
    ModeleEmail as ModeleEmail,
    PorteeExecution as PorteeExecution,
    TachePlanifiee as TachePlanifiee,
)
