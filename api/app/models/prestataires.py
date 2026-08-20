"""Prestataires, contrats d'entretien, devis et notations.

Extrait de `core.py` le 20/08/2026, au fil de l'eau : ce fichier a dépassé son
plafond en recevant `TypeEquipement.assurance` (#490), et le garde-fou de
modularité l'a refusé — à juste titre. `core.py` porte encore mille deux cents
lignes et huit domaines ; celui-ci en sort entier.

La coupe suit le domaine, pas la taille : les quatre modèles ci-dessous se
citent les uns les autres (`Prestataire` ↔ `ContratEntretien` ↔ `DevisPrestataire`
↔ `NotationPrestataire`) et ne sont cités du reste que par leurs clés
étrangères. C'est ce qui rend le déplacement sûr.

⚠️ **`core.py` doit continuer de les importer.** Un modèle défini dans un module
que personne n'a chargé n'existe pas pour `SQLModel.metadata.create_all` : la
table manquerait, sans le moindre message. C'est la raison écrite dans
`models/__init__.py`, et elle vaut ici mot pour mot.
"""
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:  # pragma: no cover — uniquement pour les annotations
    from app.models.copropriete import Copropriete


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
    #  ⚠️ Une assurance n'est PAS un équipement, et ce champ est mal nommé : il
    #  désigne en fait la CATÉGORIE d'un contrat. La notion portée par
    #  `ContratEntretien` — un contrat avec un prestataire, un numéro, une
    #  échéance, un document — est exactement celle d'un contrat d'assurance
    #  (#490). Inventer une seconde table de contrats aurait recréé le doublon
    #  que ce lot supprime ; renommer le champ toucherait quinze appels pour un
    #  gain cosmétique. On écrit la tension plutôt que de la contourner.
    assurance = "assurance"
    #: Le MANDAT du syndic. Ce n'est pas un équipement, et le nom de
    #: l'énumération est donc un peu court — mais elle porte déjà `assurance`,
    #: qui n'en est pas un non plus. Ce qu'elle classe réellement, c'est
    #: « de quoi parle ce contrat », et le mandat de syndic en relève.
    #: En ajouter une seconde pour deux valeurs aurait donné deux
    #: nomenclatures à tenir d'accord.
    syndic = "syndic"
    autre = "autre"




# ──────────────────────────────────────────────
#  FAQ
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
    cree_le: datetime = Field(default_factory=datetime.utcnow)

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

    #  ⚠️ Annotation en CHAÎNE : `Copropriete` n'est importée que sous
    #  `TYPE_CHECKING`, donc absente à l'exécution. La forme non citée
    #  fonctionne aujourd'hui — SQLModel n'évalue pas cette annotation-là —
    #  mais elle dépend d'un détail d'implémentation et d'un ordre d'import.
    #  La citer coûte deux guillemets et supprime la question.
    #  Le pendant du `foreign_keys` posé côté `Copropriete` : les deux bouts
    #  d'une relation doivent désigner le MÊME chemin, sinon SQLAlchemy en
    #  déduit deux relations qui se contredisent.
    copropriete: Optional["Copropriete"] = Relationship(
        back_populates="contrats_entretien",
        sa_relationship_kwargs={"foreign_keys": "[ContratEntretien.copropriete_id]"},
    )
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
