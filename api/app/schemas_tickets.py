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
    #  « M'envoyer une copie » — la 4e case de la Diffusion (31/08/2026).
    #  Jamais persistée : c'est une décision propre à CET envoi, pas un réglage
    #  de l'objet. La recharger cochée reviendrait à l'imposer.
    envoyer_auteur: Optional[bool] = None
    fichiers_urls: List[str] = []
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement
    #  Le périmètre que cette entrée déclare — facultatif. `None` veut dire « cette
    #  évolution ne dit rien du périmètre », et le ticket garde le sien. Quand il
    #  est fourni, il devient le périmètre COURANT du ticket (#497).
    perimetre_cible: Optional[List[str]] = None
    #  🔴 LES OPTIONS DE PUBLICATION SE CORRIGENT DEPUIS UN COMMENTAIRE
    #  (05/09/2026), demandé à l'écran :
    #
    #  > « tous les autres options de publication doivent être aussi conservé
    #  >   dans l'objet pour les tickets en édition et commentaire »
    #
    #  C'est la règle déjà posée pour l'actualité : le formulaire montre le
    #  DERNIER état, et ce qu'on enregistre DEVIENT l'état. `None` veut dire
    #  « cette entrée ne dit rien de cette option » — le ticket garde la sienne,
    #  exactement comme `perimetre_cible` juste au-dessus.
    epingle: Optional[bool] = None
    confidentiel: Optional[bool] = None
    #  🚨 « Marquer urgente » ne crée PAS de colonne : elle pilote `priorite`,
    #  que la catégorie « Urgence » met déjà à `haute`. Arbitré le 05/09/2026 —
    #  deux notions d'urgence sur le même écran finiraient par se contredire.
    urgente: Optional[bool] = None


class TicketEvolutionUpdate(BaseModel):
    contenu: Optional[str] = None
    fichiers_urls: Optional[List[str]] = None
    #  🔴 LE PÉRIMÈTRE SE CORRIGE (01/09/2026). Ce champ était refusé ici, au
    #  motif qu'« un périmètre déclaré est un fait daté ». Le raisonnement vaut
    #  pour un RESSERREMENT — « finalement, c'est le hall du bâtiment 3 » — et
    #  pas pour une FAUTE DE CLIC, qui s'écrit exactement pareil et qui coûte
    #  cher : le périmètre d'une entrée écrase celui du ticket, donc une erreur
    #  d'affectation reclasse tout le ticket.
    #
    #  ⚠️ La propagation à l'objet obéit à une règle : voir
    #  `app/utils/perimetre_fil.py`. Corriger une entrée ancienne ne doit pas
    #  défaire une précision récente.
    perimetre_cible: Optional[List[str]] = None


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
