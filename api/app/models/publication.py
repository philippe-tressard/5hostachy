"""Les ACTUALITÉS (publications) et leur historique.

Extraites de `core.py` le 15/09/2026, au fil de l'eau : ce fichier était à 933
lignes et le garde-fou de modularité (rang 1) a refusé d'y ajouter les trois
colonnes « Saisi pour ». La règle répond alors « découper avant d'ajouter », et
#779 nommait `core.py` comme cible prioritaire — la dette se paie là où on
passe, pas dans un chantier séparé qui n'arrive jamais.

La coupe suit le DOMAINE : `Publication` et `PublicationEvolution` se citent
l'une l'autre et ne sont citées du reste que par des clés étrangères. C'est ce
qui rend le déplacement sûr — même critère que `prestataires.py` le 20/08.

⚠️ **`core.py` doit continuer de les importer.** Un modèle défini dans un module
que personne n'a chargé n'existe pas pour `SQLModel.metadata.create_all` : la
table manquerait, sans le moindre message. Le réexport est là pour ça, et une
trentaine de modules écrivent encore `from app.models.core import Publication`.

⚠️ **Annotations en CHAÎNE pour `Utilisateur`**, importée sous `TYPE_CHECKING`
seulement, donc absente à l'exécution. SQLAlchemy résout la cible par son nom
dans le registre ; la forme non citée marcherait aujourd'hui — SQLModel
n'évalue pas cette annotation-là — mais elle dépend d'un détail
d'implémentation et d'un ordre d'import. La citer coûte deux guillemets et
supprime la question. C'est mot pour mot la consigne de `prestataires.py`.
"""
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:  # pragma: no cover — uniquement pour les annotations
    from app.models.core import Utilisateur


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
    #  🔴 « SAISI POUR » — au nom de qui ceci est déposé (15/09/2026).
    #
    #  Mêmes trois colonnes que `Ticket`, et ce n'est pas une recopie de
    #  commodité : c'est la MÊME notion, donc le même stockage. Un utilisateur
    #  inscrit remplit `saisi_pour_user_id` ; une personne extérieure ne laisse
    #  qu'un nom et, s'il est connu, un courriel.
    #
    #  ⚠️ **Poser ces colonnes ÉTEND un droit**, en silence si on ne le dit pas :
    #  `auth/deps.py::est_auteur` lit `saisi_pour_user_id` par `getattr`, sans
    #  connaître le type de l'objet. La personne nommée peut donc corriger ce qui
    #  parle d'elle — exactement ce que la règle veut (`ux-patterns` §15 : un
    #  membre du CS qui dépose au nom d'un résident ne le dépossède pas), mais
    #  c'est une conséquence, pas un effet de bord à découvrir.
    #
    #  ⚠️ **PAS de `foreign_key=`** : ces colonnes arrivent par `add_column` sur
    #  une table existante, et SQLite refuse d'y ajouter une contrainte. La
    #  déclarer ici ferait diverger une base neuve (`create_all`) d'une base
    #  migrée — `test_migrations.py` refuse les deux moitiés de ce défaut.
    saisi_pour_user_id: Optional[int] = Field(default=None)
    saisi_pour_nom: Optional[str] = None
    saisi_pour_email: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    publiee_le: Optional[datetime] = None
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

    auteur: Optional["Utilisateur"] = Relationship(back_populates="publications")
    evolutions: List["PublicationEvolution"] = Relationship(back_populates="publication")


class PublicationEvolution(SQLModel, table=True):
    __tablename__ = "publication_evolution"
    id: Optional[int] = Field(default=None, primary_key=True)
    publication_id: int = Field(foreign_key="publication.id")
    # type : commentaire | etat — une correction est un `commentaire` préfixé « Correction : » (#433)
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    fichiers_urls: str = "[]"  # JSON array d'URLs de fichiers joints

    publication: Optional[Publication] = Relationship(back_populates="evolutions")
    auteur: Optional["Utilisateur"] = Relationship()
