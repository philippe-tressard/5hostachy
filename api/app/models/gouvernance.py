"""L'ANNUAIRE — qui siège au conseil syndical, et qui est le syndic.

Extrait de `core.py` le 22/09/2026, au fil de l'eau : le fichier faisait 855
lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé qu'il
grossisse en recevant la fin de validité d'une actualité (#1093). La règle est
« on découpe le fichier QUAND on y touche ».

## Pourquoi CE bloc, et pas `Publication` — qui était pourtant celui qu'on touchait

🔴 **Aucun `Relationship` ici**, et c'est ce qui rend le déplacement possible :
les quatre tables ne référencent les autres que par clé étrangère nommée
(`utilisateur.id`), ce qui n'impose aucun cycle d'import.

`Publication` porte deux `Relationship` (`auteur`, `evolutions`) : la déplacer
demanderait de les résoudre par chaîne et d'importer `Utilisateur` sous
`TYPE_CHECKING`, c'est-à-dire un changement de comportement au milieu d'un lot
qui en fait déjà un. C'est la raison exacte pour laquelle `Ticket` et
`TicketEvolution` sont eux aussi restés (cf. `models/evenement.py`).

⚠️ Les noms restent **ré-exportés par `core.py`** : aucun appelant n'a une ligne
à changer, et surtout la table reste enregistrée auprès de SQLModel. Un modèle
défini dans un module que personne n'importe n'existe pas pour `create_all`, et
la table manquerait sans le moindre message.

## Les deux moitiés de l'annuaire

`AgCsInfo`/`MembreCS` disent **qui siège** — le conseil syndical, élu.
`SyndicInfo`/`MembreSyndic` disent **qui gère** — le cabinet et ses personnes.
`destinataires.py` s'appuie sur les deux, et ne les confond jamais : « le CS par
le rôle » et « le syndic principal » sont deux questions distinctes.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel

# ──────────────────────────────────────────────
#  Annuaire CS & Syndic
# ──────────────────────────────────────────────


class GenreCivilite(str, Enum):
    mr = "Mr"
    mme = "Mme"
    mlle = "Mlle"


class AgCsInfo(SQLModel, table=True):
    """Informations AG du Conseil Syndical. Un seul enregistrement (upsert)."""

    __tablename__ = "ag_cs_info"
    id: Optional[int] = Field(default=None, primary_key=True)
    ag_annee: Optional[int] = None
    ag_date: Optional[date] = None


class MembreCS(SQLModel, table=True):
    """Membre du Conseil Syndical (indépendant des comptes Utilisateur)."""

    __tablename__ = "membre_cs"
    id: Optional[int] = Field(default=None, primary_key=True)
    genre: GenreCivilite
    prenom: str
    nom: str
    batiment_id: Optional[int] = Field(default=None, foreign_key="batiment.id")
    etage: Optional[int] = None
    est_gestionnaire_site: bool = False
    est_president: bool = False
    ordre: int = 0
    user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)


class SyndicInfo(SQLModel, table=True):
    """Informations du syndic. Un seul enregistrement (upsert)."""

    __tablename__ = "syndic_info"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom_syndic: str = ""
    adresse: str = ""
    site_web: Optional[str] = None


class MembreSyndic(SQLModel, table=True):
    """Membre du syndic (indépendant des comptes Utilisateur)."""

    __tablename__ = "membre_syndic"
    id: Optional[int] = Field(default=None, primary_key=True)
    genre: GenreCivilite
    prenom: str
    nom: str
    fonction: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None  # CSV comma-separated, même pattern que Prestataire
    est_principal: bool = False
    ordre: int = 0
    user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
