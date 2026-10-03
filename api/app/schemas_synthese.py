"""Les schémas de la synthèse d'une affaire close (#1643).

`SyntheseLue` est partagée par deux lecteurs — la fiche de l'affaire
(`routers/tickets/synthese`) et le carnet d'entretien (`utils/carnet_entretien`) —,
donc dans un fichier de domaine, ré-exporté par `schemas.py`. Les corps des
gestes, propres au routeur, vivent à côté de lui (`synthese_schemas.py`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class SyntheseLue(BaseModel):
    """Une synthèse telle que l'écran et le carnet la lisent."""

    id: int
    ticket_id: int
    evolution_id: Optional[int] = None
    statut: str
    #: Les métriques FIGÉES à la production (`utils/synthese_affaire/metriques`).
    metriques: Optional[dict[str, Any]] = None
    synthese: Optional[str] = None
    difficultes: Optional[str] = None
    amelioration: Optional[str] = None
    prompt_complement: Optional[str] = None
    assiste_ia: bool = False
    motif_vide: Optional[str] = None
    produite_le: Optional[datetime] = None
    validee_le: Optional[datetime] = None
    validee_par_nom: Optional[str] = None

    class Config:
        from_attributes = True
