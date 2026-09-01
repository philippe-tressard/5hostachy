"""Le CALENDRIER — un événement, et le fil de son suivi.

Créé le 18/08/2026, sur demande : *« pour Calendrier il doit y avoir un
historique et workflow »*. Le **workflow existait déjà** sous un autre nom — les
colonnes du Kanban (AG · CS · Syndic · Prestataire · Terminé · Annulé) répondent
exactement à la question de la section 3 du cadre #430, *« où en est cet
objet ? »*. Ce qui manquait, c'était la **trace** : une colonne changeait sans
que rien ne dise quand, par qui, ni pourquoi.

## Pourquoi un module à part

⚠️ Ce module ne portait que l'HISTORIQUE jusqu'au 19/08/2026 — `Evenement`
lui-même était resté dans `core.py`, qui a donc continué de grossir pendant
qu'un module portant son nom existait à côté. Les trois déclarations
(`TypeEvenement`, `StatutKanban`, `Evenement`) l’ont rejoint quand le garde-fou
a de nouveau refusé une ligne à `core.py` (#497).

⚠️ Aucun `Relationship` ici, et c'est ce qui rend le déplacement possible :
`Evenement` ne référence les autres tables que par clé étrangère nommée
(`batiment.id`, `utilisateur.id`, `prestataire.id`), ce qui n'impose aucun
cycle d'import. C'est la raison exacte pour laquelle `Ticket` et
`TicketEvolution`, eux, restent dans `core.py` (cf. `models/tickets.py`).

`core.py` fait 1 237 lignes et le garde-fou de modularité (rang 1,
`standards/02` §6) refuse qu'un fichier au-delà de 500 grossisse pour une
nouvelle fonctionnalité. Même raison que `models/tickets.py` (17/08) et
`models/copropriete.py` (13/08).

⚠️ Ce module doit être **importé** par `models/__init__.py` : un modèle que
personne n'a importé n'existe pas pour `metadata.create_all`, et la table
manquerait sans le moindre message.

## La forme est celle des deux autres fils, et c'est délibéré

`TicketEvolution` et `PublicationEvolution` portent les mêmes colonnes. Les trois
alimentent la **même** rubrique d'affichage (`RubriqueHistorique.svelte`), qui ne
connaît aucune entité — elle attend `type`, `contenu`, `ancien_statut`,
`nouveau_statut`, `auteur_nom`, `cree_le`, `fichiers_urls`. Diverger ici aurait
obligé à lui ajouter une variante, et *une variante ajoutée pour accueillir un
écart existant ne factorise pas : elle entérine*.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


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
    #  🔴 La SOURCE de la visite, quand elle vient du pré-remplissage du kanban
    #  (#605, point 2). Le rapprochement se faisait sur le titre littéral : le
    #  renommer — ou renommer le prestataire — recréait tout l'exercice en double.
    #
    #  ⚠️ Nullable, et ça le reste : les visites créées AVANT le 01/09/2026 n'en
    #  ont pas, et un événement de maintenance saisi à la main n'a pas de contrat.
    #  ⚠️ PAS de `foreign_key=` : SQLite ne sait pas ajouter une contrainte à une
    #  table existante, et la migration 0165 a crashé en production pour l'avoir
    #  tenté. Une base neuve et une base migrée doivent porter le même schéma —
    #  le déclarer ici et pas là ferait diverger les deux en silence.
    contrat_id: Optional[int] = Field(default=None)
    frequence_type: Optional[str] = Field(default=None)   # "semaines", "mois", "fois_par_an"
    frequence_valeur: Optional[int] = Field(default=None)
    affichable: bool = Field(default=False)  # visible dans le dashboard (évènements récents)
    # Même convention que Ticket.photos_urls (tableau JSON d'URLs internes) : le
    # modèle portait déjà trois noms pour la même notion, ne pas en créer un 4ᵉ.
    photos_urls: Optional[str] = None  # JSON array of photo URLs
    # Pièces jointes non-images, même convention que Ticket.fichiers_urls.
    fichiers_urls: str = "[]"  # JSON array d'URLs de fichiers joints
    epingle: bool = False  # même notion que Publication.epingle
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False


class EvenementEvolution(SQLModel, table=True):
    __tablename__ = "evenement_evolution"

    id: Optional[int] = Field(default=None, primary_key=True)
    evenement_id: int = Field(foreign_key="evenement.id")
    #  type : commentaire | etat — et deux seulement, comme pour les tickets et
    #  les publications. Une CORRECTION s'inscrit en `commentaire` préfixé
    #  « Correction : » ; seule une transition volontaire du Kanban est un `etat`.
    type: str
    contenu: Optional[str] = None
    #  Les deux colonnes du Kanban, avant et après. Renseignées pour un `etat`,
    #  nulles pour tout le reste — c'est leur absence qui distingue une correction
    #  d'une étape du suivi, et c'est ce que le fil lit pour ne pas dessiner un
    #  jalon là où il n'y en a pas.
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int = Field(foreign_key="utilisateur.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    #  Tableau JSON d'URLs internes — même convention que `Ticket.photos_urls`.
    fichiers_urls: str = "[]"
