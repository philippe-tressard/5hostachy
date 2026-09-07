"""Les schémas d'ENTRÉE et de SORTIE des publications — actualités et leur fil.

Sortis de `schemas.py` le 05/09/2026, sur refus du contrôle de modularité : le
fichier dépassait 500 lignes et grossissait encore, en accueillant le ciblage
porté par une entrée du fil. La découpe suit celle qui existait déjà pour les
tickets (`schemas_tickets`), et `schemas.py` les **ré-exporte** : aucun import
n'a à changer ailleurs.

⚠️ `PublicationEvolutionUpdate` est resté dans `schemas.py` : il y est déclaré
avant les imports de fin de fichier, et l'y laisser évite un cycle.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

from app.schemas_communs import ListeJson

class PublicationCreate(BaseModel):
    titre: str
    contenu: str
    perimetre: str = "résidence"
    batiment_id: Optional[int] = None
    epingle: bool = False
    urgente: bool = False
    photos_urls: ListeJson = []
    perimetre_cible: List[str] = ["résidence"]
    public_cible: List[str] = ["résidents"]
    statut: Optional[str] = "publie"
    brouillon: bool = False
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False
    #  🔴 « Envoyer une copie à … » — la 4e case de la Diffusion (31/08/2026).
    #
    #  Elle s'affichait déjà sur cet écran, `CanauxNotification` la posant pour
    #  les huit formulaires qui emploient la Diffusion. Mais **seuls les tickets
    #  la lisaient** : ici, la cocher n'avait aucun effet, et rien ne le disait.
    #
    #  ⚠️ C'est exactement ce que le cadre interdit — *« avant de rouvrir un
    #  champ dans l'interface, vérifier que le serveur le CONSOMME »*. Le
    #  contrôle `lint:diffusion-auteur` ne voyait pas le trou : les écrans
    #  concernés ne lient pas la case eux-mêmes, ils la reçoivent de
    #  `ChampsCommuns`, qui figurait sur sa liste de relais.
    envoyer_auteur: bool = False
    annonce_hall: bool = False  # génère l'affiche de hall + envoi au CS du périmètre
    confidentiel: bool = False  # lecture réservée au périmètre visé (#347)
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement


class PublicationUpdate(BaseModel):
    titre: Optional[str] = None
    contenu: Optional[str] = None
    epingle: Optional[bool] = None
    urgente: Optional[bool] = None
    photos_urls: Optional[ListeJson] = None
    batiment_id: Optional[int] = None
    perimetre_cible: Optional[List[str]] = None
    public_cible: Optional[List[str]] = None
    statut: Optional[str] = None
    brouillon: Optional[bool] = None
    archivee: Optional[bool] = None
    partager_whatsapp: Optional[bool] = None
    envoyer_syndic: Optional[bool] = None
    envoyer_cs: Optional[bool] = None
    #  Voir `PublicationCreate` : la case ne se stocke pas, c'est une intention
    #  d'envoi. À la mise à jour elle vaut pour CET enregistrement.
    envoyer_auteur: Optional[bool] = None
    annonce_hall: Optional[bool] = None
    #  Modifiable après publication, volontairement : c'est ce qui permet de
    #  rattraper une actualité publiée au mauvais périmètre. Elle disparaît alors
    #  du fil des autres périmètres — ceux qui l'ont lue l'ont lue (arbitrage #347).
    confidentiel: Optional[bool] = None


class EvolutionRead(BaseModel):
    id: int
    publication_id: int
    type: str
    contenu: Optional[str] = None
    ancien_statut: Optional[str] = None
    nouveau_statut: Optional[str] = None
    auteur_id: int
    auteur_nom: Optional[str] = None
    cree_le: datetime
    fichiers_urls: ListeJson = []

    class Config:
        from_attributes = True


class EvolutionCreate(BaseModel):
    type: str  # commentaire | etat | correction
    contenu: Optional[str] = None
    nouveau_statut: Optional[str] = None  # requis si type=="etat"
    partager_whatsapp: Optional[bool] = None  # None = hérite de la publication
    envoyer_syndic: Optional[bool] = None  # None = hérite de la publication
    envoyer_cs: Optional[bool] = None  # None = hérite de la publication
    fichiers_urls: List[str] = []
    email_externe: Optional[str] = None  # adresse libre, CS/Admin uniquement
    #  🔴 LE CIBLAGE ET LES OPTIONS DE LA PUBLICATION, portés par l'entrée
    #  (05/09/2026). Demandé à l'écran : *« les sections Options de publication,
    #  Périmètre et Destinataires doivent être visibles même pour chaque
    #  commentaire ; tu remets le dernier état, et le nouveau sauvegardé deviendra
    #  validé »*.
    #
    #  ⚠️ Ces champs ne décrivent PAS l'entrée : ils décrivent la publication, et
    #  c'est elle qu'ils modifient. Ils voyagent avec l'entrée pour qu'un seul
    #  aller-retour valide les deux — deux requêtes laisseraient l'une passer et
    #  l'autre non, et l'écran ne saurait plus quoi afficher.
    #
    #  `None` = « je n'ai rien dit », et c'est la valeur par défaut : un client qui
    #  ignore ces champs — un vieux bundle resté en cache — ne touche à rien. Une
    #  liste vide, elle, serait un effacement délibéré.
    perimetre_cible: Optional[List[str]] = None
    public_cible: Optional[List[str]] = None
    epingle: Optional[bool] = None
    urgente: Optional[bool] = None
    brouillon: Optional[bool] = None
    confidentiel: Optional[bool] = None


class PublicationRead(BaseModel):
    id: int
    titre: str
    contenu: str
    perimetre: str
    batiment_id: Optional[int] = None
    epingle: bool
    urgente: bool
    auteur_id: int
    photos_urls: ListeJson = []
    cree_le: datetime
    mis_a_jour_le: Optional[datetime] = None
    perimetre_cible: List[str] = ["résidence"]
    public_cible: List[str] = ["résidents"]
    statut: Optional[str] = None
    statut_change_le: Optional[datetime] = None
    brouillon: bool = False
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False
    annonce_hall: bool = False
    confidentiel: bool = False
    evolutions: List[EvolutionRead] = []
    auteur_nom: Optional[str] = None

    @field_validator('perimetre_cible', 'public_cible', mode='before')
    @classmethod
    def parse_json_list(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [v] if v else []
        return v or []

    class Config:
        from_attributes = True


