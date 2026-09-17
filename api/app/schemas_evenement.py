"""Les schémas d'ENTRÉE et de SORTIE des événements du calendrier.

Sortis de `routers/calendrier.py` le 17/09/2026, sur refus du contrôle de
modularité : le fichier repassait au-dessus de 500 lignes en recevant la marque
`assiste_ia` (#985). La découpe suit celle des publications
(`schemas_publications`) et des tickets (`schemas_tickets`) ; `calendrier.py`
les ré-exporte, et les importateurs existants n'ont pas changé.

⚠️ `EvolutionEvenementRead` vient de `calendrier_historique`, qui n'importe
`calendrier` que de façon différée (dans une fonction) : pas de cycle.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from app.models.core import TypeEvenement
from app.routers.calendrier_historique import EvolutionEvenementRead
from app.utils.assiste_ia import AssisteIACorrection, AssisteIAEntree, AssisteIASortie
from app.utils.saisi_pour import SaisiPourEntree, SaisiPourSortie

__all__ = ["EvenementCreate", "EvenementRead", "EvenementUpdate", "EvolutionEvenementRead"]


class EvenementCreate(SaisiPourEntree, AssisteIAEntree):
    titre: str
    description: Optional[str] = None
    type: TypeEvenement = TypeEvenement.autre
    lieu: Optional[str] = None
    debut: datetime
    fin: Optional[datetime] = None
    perimetre: str = "résidence"
    batiment_id: Optional[int] = None
    statut_kanban: Optional[str] = None
    prestataire_id: Optional[int] = None
    #  La SOURCE d'une visite pré-remplie — le rapprochement se faisait sur le
    #  titre littéral, qu'un renommage faisait perdre (#605, point 2).
    contrat_id: Optional[int] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: bool = True
    epingle: bool = False
    #  🛡️ Réservé au conseil syndical (#939) — la règle de LECTURE vit dans
    #  `evenement_visible`, jamais ici : ce schéma ne fait que transporter.
    reserve_cs: bool = False
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None
    envoyer_cs: Optional[bool] = None
    #  « Envoyer une copie à … » — la 4e case de la Diffusion (31/08/2026).
    #  Elle s'affichait sur cet écran sans être lue nulle part. Le destinataire
    #  est l'auteur de l'OBJET, pas celui qui écrit : le CS qui reprend un
    #  ticket décide alors de notifier le résident qui l'a ouvert.
    envoyer_auteur: Optional[bool] = None
    # Pièces jointes déjà téléversées via POST /uploads/fichier. Les fournir dès
    # la création est ce qui permet à l'e-mail syndic/CS de partir avec.
    photos_urls: list[str] = []
    fichiers_urls: list[str] = []


class EvenementRead(SaisiPourSortie, AssisteIASortie):
    id: int
    titre: str
    description: Optional[str] = None
    type: str
    lieu: Optional[str] = None
    debut: datetime
    fin: Optional[datetime] = None
    perimetre: str
    batiment_id: Optional[int] = None
    auteur_id: int
    auteur_nom: Optional[str] = None
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None
    statut_kanban: Optional[str] = None
    prestataire_id: Optional[int] = None
    contrat_id: Optional[int] = None
    prestataire_nom: Optional[str] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: bool = True
    #: État EFFECTIF : archivé à la main, **ou** par la règle du site — 30 jours
    #: après la fin de l'événement, immédiat s'il est annulé, jamais s'il est
    #: épinglé (`utils/archivage`, #515). C'est ce que l'écran emploie.
    #:
    #: 🔴 Le calendrier le calculait LUI-MÊME, et divergeait sur trois points :
    #: l'annulation n'y était pas immédiate, l'épinglage n'y protégeait pas, et
    #: surtout le délai réglé en administration ne l'atteignait jamais — la clé
    #: `archivage_delai_jours` n'est pas dans la liste blanche de `GET /config`,
    #: donc l'écran tournait depuis toujours sur son défaut en dur.
    archivee: bool = False
    #: La DÉCISION HUMAINE, seule — la colonne. Même séparation que l'affiche de
    #: hall : elle dit si « désarchiver » aurait un effet.
    archivee_manuellement: bool = False
    epingle: bool = False
    reserve_cs: bool = False
    # Stocké en colonne comme un tableau JSON (convention Ticket.photos_urls) ;
    # exposé en liste pour que le front n'ait rien à désérialiser.
    photos_urls: list[str] = []
    fichiers_urls: list[str] = []
    #  L'HISTORIQUE, livré avec l'événement : le fil est court (quelques entrées)
    #  et la carte l'affiche dès qu'elle est dépliée. Un second appel par
    #  événement aurait fait autant de requêtes que de lignes à l'écran.
    evolutions: list["EvolutionEvenementRead"] = []

    class Config:
        from_attributes = True


class EvenementUpdate(SaisiPourEntree, AssisteIACorrection):
    titre: Optional[str] = None
    description: Optional[str] = None
    type: Optional[TypeEvenement] = None
    lieu: Optional[str] = None
    debut: Optional[datetime] = None
    fin: Optional[datetime] = None
    perimetre: Optional[str] = None
    batiment_id: Optional[int] = None
    statut_kanban: Optional[str] = None
    archivee: Optional[bool] = None
    prestataire_id: Optional[int] = None
    frequence_type: Optional[str] = None
    frequence_valeur: Optional[int] = None
    affichable: Optional[bool] = None
    epingle: Optional[bool] = None
    reserve_cs: Optional[bool] = None
    # Sert uniquement à RETIRER des photos : l'ajout passe par l'endpoint
    # d'upload, seul capable de valider et de redimensionner le fichier.
    photos_urls: Optional[list[str]] = None
    # Idem pour les documents : POST /uploads/fichier valide le type MIME, ce
    # champ ne fait que fixer la liste finale.
    fichiers_urls: Optional[list[str]] = None
