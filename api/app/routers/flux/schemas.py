"""Flux — contrat de sortie de l'endpoint.

Extrait de `flux.py` le 08/08/2026, sans modification. Voir `__init__.py` pour
la règle de découpage.

Ces trois modèles sont le **contrat avec le front** : `FluxCard` et
`FluxVignette` lisent `meta` par clé. Ajouter une rubrique n'autorise pas à
inventer une clé de plus pour une notion qui en a déjà une — une photo se
transmet sous `photos_urls`, partout, sinon la rubrique est la seule à ne pas
avoir d'aperçu.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class FluxItem(BaseModel):
    id: str = ""         # e.g. "ev_42", "tk_15", "pub_7", "dv_3", "sond_1"
    type: str            # ticket_resolu, ticket_ouvert, publication, evenement, devis, sondage_clos, sondage_ouvert
    date: datetime
    cree_le: Optional[datetime] = None
    titre: str
    detail: Optional[str] = None
    badges: list[str] = []
    icon: str = ""
    lien: Optional[str] = None
    meta: dict = {}


class FluxSante(BaseModel):
    tickets_ouverts: int = 0
    tickets_urgents: int = 0
    resolution_moyenne_heures: Optional[float] = None
    sondages_actifs: int = 0
    validations_cs: int = 0
    tickets_relance_syndic: int = 0
    prochains: list[dict] = []


class FluxResponse(BaseModel):
    items: list[FluxItem] = []
    sante: FluxSante = FluxSante()


class EpinglesCompte(BaseModel):
    total: int = 0
    publications: int = 0
    evenements: int = 0
