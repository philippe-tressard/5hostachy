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


# ── Les moyennes d'un ENSEMBLE d'affaires closes (#1645, #1646) ─────────────────
#  Partagées par deux routeurs — le bilan du carnet (`routers/carnet`) et la fiche
#  d'un prestataire (`routers/prestataires_metriques`) : d'où ce fichier de domaine.
#  Le calcul vit dans `utils/synthese_affaire/agregats`.


class EtapeMoyenne(BaseModel):
    """Une étape du kanban : sa durée moyenne, et combien d'affaires y sont passées."""

    statut: str
    #: Jours ouvrés, au demi-jour.
    jours: float
    nombre: int


class ResumeAffaires(BaseModel):
    """Les moyennes d'un ensemble d'affaires closes — `None` quand rien ne se mesure."""

    nombre: int
    annulees: int
    duree_totale: Optional[float] = None
    etapes: list[EtapeMoyenne] = []
    #: Le TOTAL des relances au syndic ; la moyenne par affaire à côté.
    relances: int
    relances_par_affaire: Optional[float] = None
    #: Délai moyen de réaction du syndic après la dernière relance, et sur combien.
    reaction_relance: Optional[float] = None
    reactions: int
    premiere_reponse_syndic: Optional[float] = None
    suites: Optional[float] = None


class ExerciceLu(BaseModel):
    """Un exercice comptable : l'année où il commence, et son nom (« 2025-2026 »)."""

    annee: int
    libelle: str
