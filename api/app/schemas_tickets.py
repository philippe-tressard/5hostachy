"""Les schémas d'un TICKET et de son fil de suivi.

Extraits de `schemas.py` le 19/08/2026, au fil de l'eau : le fichier venait de
franchir les 500 lignes et le garde-fou de modularité (rang 1) a refusé qu'il
grossisse pour recevoir `perimetre_cible` sur une évolution (#497). La règle est
« on découpe le fichier QUAND on y touche » — et c'est bien aux évolutions de
ticket qu'on touchait.

Même geste que `models/tickets.py` (17/08) et `models/evenement.py` : les noms
restent **ré-exportés par `schemas.py`**, donc aucun des routeurs appelants n'a
une ligne à changer.

⚠️ N'importe que `schemas_communs` et `models.core` — jamais `schemas`, qui
l'importe. Un cycle ferait dépendre le démarrage de l'ordre des imports.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.models.core import StatutTicket
from app.schemas_communs import ListeJson



class TicketEvolutionCreate(BaseModel):
    type: str  # commentaire | etat
    contenu: Optional[str] = None
    #  Même type que `TicketUpdate.statut`, donc **même verdict** : les deux
    #  chemins de changement d'état d'un ticket valident désormais la même
    #  chose, au même endroit. `_STATUTS_ADMIS` — la liste écrite à la main qui
    #  refusait `annulé` depuis toujours — a disparu du routeur (#415).
    nouveau_statut: Optional[StatutTicket] = None
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None
    envoyer_cs: Optional[bool] = None
    fichiers_urls: List[str] = []
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement
    #  Le périmètre que cette entrée déclare — facultatif. `None` veut dire « cette
    #  évolution ne dit rien du périmètre », et le ticket garde le sien. Quand il
    #  est fourni, il devient le périmètre COURANT du ticket (#497).
    perimetre_cible: Optional[List[str]] = None


class TicketEvolutionUpdate(BaseModel):
    contenu: Optional[str] = None
    fichiers_urls: Optional[List[str]] = None
    #  ⚠️ Pas de `perimetre_cible` ici, et c'est délibéré : un périmètre déclaré est
    #  un fait daté. On en déclare un nouveau, on ne rature pas l'ancien — sinon
    #  l'historique du resserrement, qui est tout l'intérêt, disparaît.


class TicketEvolutionRead(BaseModel):
    id: int
    ticket_id: int
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int
    auteur_nom: Optional[str] = None
    cree_le: datetime
    fichiers_urls: ListeJson = []
    #  `None` quand l'entrée ne parle pas du périmètre — à distinguer d'une liste
    #  vide, qui voudrait dire « plus aucun périmètre ».
    perimetre_cible: Optional[ListeJson] = None

    class Config:
        from_attributes = True
