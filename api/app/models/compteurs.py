"""Les **compteurs** de la résidence — relevés et configuration.

Extraites de `models/core.py` le 21/09/2026 (modularité, rang 1). Ce fichier-là
était à 831 lignes, et le contrôle a refusé qu'il grossisse d'une colonne : la
règle est « on découpe QUAND on y touche ».

⚠️ **Ces deux tables-ci parce qu'elles ne portent aucune `Relationship`.** Le
lot qui les a déplacées parlait d'autre chose (la promotion d'une actualité en
affaire, #1094) : il fallait un découpage qui ne puisse rien casser, et
l'absence de relation le garantissait. `core.py` les ré-exporte, donc aucun
import existant ne bouge.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ReleveCompteur(SQLModel, table=True):
    __tablename__ = "releve_compteur"
    id: Optional[int] = Field(default=None, primary_key=True)
    type_compteur: str  # "eau_general", …
    date_releve: date = Field(default_factory=date.today)
    index: Optional[int] = None  # index lu (None si non relevé / changement)
    note: Optional[str] = None  # ex : "Changement compteur"
    photo_url: Optional[str] = None
    prestataire_id: Optional[int] = Field(default=None, foreign_key="prestataire.id")
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    cree_par_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")


# ──────────────────────────────────────────────
#  Configuration des compteurs (consommations)
# ──────────────────────────────────────────────


class CompteurConfig(SQLModel, table=True):
    __tablename__ = "compteur_config"
    id: Optional[int] = Field(default=None, primary_key=True)
    type_compteur: str = Field(index=True)  # slug unique ex: "eau_general"
    label: str  # ex: "💧 Compteur EAU Général"
    prestataire_id: Optional[int] = Field(default=None, foreign_key="prestataire.id")
    actif: bool = True
    ordre: int = 0  # for display order
