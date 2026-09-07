"""Les demandes qu'une administration doit **trancher** — accès, profil.

Extraites de `core.py` le 17/08/2026, au fil de l'eau : le fichier faisait 1 269
lignes et le garde-fou de modularité (rang 1, `standards/02` §6) a refusé qu'il
grossisse pour recevoir `Utilisateur.decision_compte_le` (#399). La règle est
« on découpe le fichier QUAND on y touche ».

Le périmètre retenu est la **rubrique**, pas un intervalle de lignes : ces deux
files vivaient à 900 lignes l'une de l'autre dans `core.py` alors qu'elles sont
la même notion — une demande déposée par un résident, qui attend une décision, et
qui alimente les mêmes écrans (l'onglet « Comptes & accès » de l'Espace CS, la
file de `/admin`) et le même compteur de tableau de bord.

La **troisième** file, les comptes en attente de validation, n'a pas de table à
elle : c'est un état de `Utilisateur`, qui reste dans `core.py` avec le reste du
modèle. La question « ce compte attend-il une décision ? » vit, elle, dans
`app/utils/comptes.py` — un seul endroit, parce qu'elle était écrite trois fois.

Même geste que `copropriete.py` (13/08), `annonce_hall.py` (15/08) et
`communaute.py` (16/08), et même précaution : les noms restent **ré-exportés par
`core.py`**, si bien qu'aucun module appelant n'a une ligne à changer. C'est
aussi ce qui garantit que les tables restent enregistrées dans les métadonnées
SQLModel — un modèle défini dans un module que personne n'importe n'existe pas
pour `create_all`, ni pour Alembic.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel

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
