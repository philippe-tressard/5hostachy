"""L'HISTORIQUE d'un événement de calendrier — le fil de son suivi.

Créé le 18/08/2026, sur demande : *« pour Calendrier il doit y avoir un
historique et workflow »*. Le **workflow existait déjà** sous un autre nom — les
colonnes du Kanban (AG · CS · Syndic · Prestataire · Terminé · Annulé) répondent
exactement à la question de la section 3 du cadre #430, *« où en est cet
objet ? »*. Ce qui manquait, c'était la **trace** : une colonne changeait sans
que rien ne dise quand, par qui, ni pourquoi.

## Pourquoi un module à part

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
from typing import Optional

from sqlmodel import Field, SQLModel


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
