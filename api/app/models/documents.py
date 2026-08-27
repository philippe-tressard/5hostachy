"""Modèles de la BIBLIOTHÈQUE DOCUMENTAIRE — profils d'accès, catégories, documents.

⚠️ Fragment de `app/models/` — extrait de `core.py` le 27/08/2026 (modularité,
rang 1 : `core.py` était à 1 108 lignes et la règle est « on découpe le fichier
QUAND on y touche »). La surface publique NE BOUGE PAS : `core.py` les réexporte,
et les modules qui écrivent `from app.models.core import Document` — ils sont une
vingtaine — n'ont pas une ligne à changer.

La couture est réelle et non un point de coupe arbitraire : ces trois classes
forment l'algorithme d'accès aux documents, celui que `utils/visibility/documents.py`
implémente à lui seul. `Document` est le seul modèle du site dont la lecture passe
par un contrôle à trois couches.

⚠️ Ce module N'IMPORTE PAS `core.py`, et il ne doit jamais le faire : `core.py`
l'importe. Les clés étrangères sont déclarées par CHAÎNE (`foreign_key="ticket.id"`),
ce qui n'exige aucun import — c'est ce qui rend le découpage possible sans cycle.
"""
from datetime import date, datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


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
    publication_id: Optional[int] = Field(default=None, foreign_key="publication.id")
    #  Pièces jointes de ticket et d'événement (#390, migration 0158). Une pièce
    #  jointe déposée dans une ÉVOLUTION appartient à son PORTEUR — les trois
    #  tables d'évolution en ont chacune un —, jamais à l'évolution elle-même.
    ticket_id: Optional[int] = Field(default=None, foreign_key="ticket.id")
    evenement_id: Optional[int] = Field(default=None, foreign_key="evenement.id")
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
