"""Modèles de la rubrique **Communauté** — sondages, petites annonces, idées.

Extraits de `core.py` le 16/08/2026, au fil de l'eau : le fichier faisait 1 415
lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé qu'il
grossisse en recevant le ciblage standard du sondage. La règle est « on découpe
le fichier QUAND on y touche ».

Le périmètre retenu est la RUBRIQUE, pas un intervalle de lignes : ses morceaux
ne se suivaient pas dans `core.py` — l'annuaire CS et les diagnostics étaient
intercalés, et y restent. Un premier découpage contigu les avait emportés, ce
qui aurait produit un module dont le nom mentait sur le contenu.

Même geste que `copropriete.py` (13/08) et `annonce_hall.py` (15/08), et même
précaution : les noms restent **ré-exportés par `core.py`**, si bien qu'aucun des
modules appelants n'a une ligne à changer. C'est aussi ce qui garantit que les
tables restent enregistrées dans les métadonnées SQLModel — un modèle défini dans
un module que personne n'importe n'existe pas pour Alembic.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel

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
    #  Ciblage : None/vide = tous. MÊMES deux champs que `Publication`, et c'est
    #  le point — le sondage avait les siens (`batiments_ids`, `profils_autorises`),
    #  seul de tout le site, si bien qu'on ne pouvait cibler ni le parking, ni
    #  l'AFUL, ni un espace de bâtiment. Unifié le 16/08/2026 (migration 0147).
    perimetre_cible: Optional[str] = Field(default=None)  # JSON de codes de périmètre
    public_cible: Optional[str] = Field(default=None)     # JSON de codes de public
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
    """Le WORKFLOW d'une annonce — arbitré le 18/08/2026.

    🔴 Contredit la déclaration de la veille (`front/src/lib/entites/annonce.ts`),
    qui posait `sansObjet` sur la section 3 : *« une annonce n'a pas d'étapes de
    vie suivies à plusieurs »*. C'était mon arbitrage, pas celui du produit —
    l'utilisateur a tranché l'inverse, et la déclaration a été corrigée avec.

    ⚠️ `archive` n'en fait PAS partie, et c'est délibéré : l'archivage n'est pas
    une étape que quelqu'un choisit, c'est une conséquence du temps. Il se
    CALCULE (`_est_archivee`), comme pour les actualités. En faire un sixième
    état aurait donné deux notions pour la même chose — celle qu'on pose et
    celle qui arrive — libres de se contredire.
    """

    en_cours = "en_cours"
    reserve = "reserve"
    vendu = "vendu"
    donne = "donne"
    annule = "annule"


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
    #  Le PÉRIMÈTRE — section 4 du cadre #430. Ajouté le 18/08/2026 sur demande
    #  utilisateur : une annonce n'était PAS sans périmètre, elle était sans
    #  MOYEN d'en porter un. Le formulaire disait « l'annonce n'a ni périmètre
    #  ni destinataires : elle s'adresse à tous les résidents par nature » — une
    #  absence de notion que l'écran avait décrétée, pas le produit.
    #
    #  ⚠️ Même forme que `Publication.perimetre_cible` et `Evenement.perimetre` :
    #  du JSON de codes (`["résidence"]`, `["bat:1","parking"]`), pas un texte
    #  libre. La forme se recopie parce que la NOTION est la même — c'est
    #  `PerimetrePicker` et `perimetreLabel` qui la lisent, et ils ne savent lire
    #  que celle-là.
    perimetre_cible: Optional[str] = Field(default='["résidence"]')
    statut: StatutAnnonce = StatutAnnonce.en_cours
    #  🔴 L'horodatage du DERNIER CHANGEMENT D'ÉTAT, et non de la dernière
    #  modification. C'est lui qui décide de l'archivage automatique à un mois.
    #
    #  ⚠️ Mesurer sur `mis_a_jour_le` aurait paru équivalent et ne l'est pas :
    #  corriger une faute de frappe sur une annonce vendue repousserait son
    #  archivage d'un mois, indéfiniment, à chaque retouche. `Publication` porte
    #  le même champ (`statut_change_le`) pour exactement cette raison.
    statut_change_le: Optional[datetime] = None
    contact_visible: bool = True  # autoriser affichage email/prénom-nom
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    mis_a_jour_le: Optional[datetime] = None


class CommentaireSondage(SQLModel, table=True):
    __tablename__ = "commentaire_sondage"
    id: Optional[int] = Field(default=None, primary_key=True)
    sondage_id: int = Field(foreign_key="sondage.id")
    auteur_id: int = Field(foreign_key="utilisateur.id")
    contenu: str
    cree_le: datetime = Field(default_factory=datetime.utcnow)


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


class ReponseCommunaute(SQLModel, table=True):
    """Réponse à un contenu de la Communauté — table générique factorisée.

    rubrique = 'idee' | 'annonce' ; cible_id = id de l'idée ou de l'annonce.
    Les commentaires de sondage restent dans CommentaireSondage (legacy, avec
    sémantique « commentaire attaché au vote »), mais partagent les mêmes
    helpers d'enrichissement/notification et le même composant front.
    """
    __tablename__ = "reponse_communaute"
    id: Optional[int] = Field(default=None, primary_key=True)
    rubrique: str = Field(index=True)          # 'idee' | 'annonce'
    cible_id: int = Field(index=True)          # id de l'idée / annonce (polymorphe)
    auteur_id: int = Field(foreign_key="utilisateur.id")
    contenu: str
    cree_le: datetime = Field(default_factory=datetime.utcnow)


class Signalement(SQLModel, table=True):
    """Signalement d'un contenu Communauté inapproprié → file de modération CS.

    cible_type : 'idee' | 'annonce' | 'sondage' | 'reponse' (ReponseCommunaute)
                 | 'commentaire' (CommentaireSondage).
    """
    __tablename__ = "signalement"
    id: Optional[int] = Field(default=None, primary_key=True)
    cible_type: str = Field(index=True)
    cible_id: int = Field(index=True)
    apercu: str = ""                            # extrait/titre du contenu (pour la file)
    auteur_cible_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    signale_par_id: int = Field(foreign_key="utilisateur.id")
    motif: str
    statut: str = Field(default="en_attente")  # en_attente | traite | rejete
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    traite_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    traite_le: Optional[datetime] = None
