"""Les schémas de la commande d'un accès par un résident.

Sortis de `app/schemas.py` (#1566) : seul `resident.py` s'en sert.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CommandeAccesCreate(BaseModel):
    lot_id: int
    type: str  # vigik | telecommande
    quantite: int = 1
    motif: Optional[str] = None


class CommandeAccesRead(BaseModel):
    id: int
    user_id: int
    lot_id: int
    type: str
    quantite: int
    motif: Optional[str] = None
    statut: str
    cree_le: datetime

    class Config:
        from_attributes = True
