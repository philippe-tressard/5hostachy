"""Modèles de la télémétrie d'usage et de son agrégation.

Extraits de `models/core.py` le 12/08/2026 en y ajoutant la colonne `noeud`
(#312) : ce fichier atteignait 1545 lignes et le garde-fou de modularité — rang
1, sans exception — refuse qu'un fichier de plus de 500 lignes grossisse. La
règle est « on découpe QUAND on y touche », et c'est ce domaine-ci que ce lot
touchait.

Ces quatre modèles forment un ensemble autonome : aucune clé étrangère, aucun
type partagé avec le reste des modèles. C'est ce qui rend l'extraction sûre.

⚠️ `core.py` les réimporte, donc `from app.models.core import TelemetryEvent`
continue de fonctionner — c'est la forme utilisée partout, et un lot de
découpage n'a pas à réécrire ses appelants. L'import y est aussi ce qui
enregistre ces tables dans les métadonnées SQLModel : le retirer les ferait
disparaître de la création de schéma.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

# ──────────────────────────────────────────────
#  Télémétrie
# ──────────────────────────────────────────────

class TelemetryEvent(SQLModel, table=True):
    """Événement brut de télémétrie — conservé 30 jours puis agrégé."""
    __tablename__ = "telemetry_event"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="utilisateur.id")
    page: str = Field(index=True)          # ex: /actualites, /tickets
    action: str = "view"                    # view | click | submit
    detail: Optional[str] = None            # ex: bouton cliqué, id ticket
    cree_le: datetime = Field(default_factory=datetime.utcnow, index=True)


class TelemetryDaily(SQLModel, table=True):
    """Agrégation journalière — conservée 12 mois."""
    __tablename__ = "telemetry_daily"
    id: Optional[int] = Field(default=None, primary_key=True)
    jour: str = Field(index=True)           # YYYY-MM-DD
    page: str
    action: str = "view"
    utilisateurs_uniques: int = 0
    total: int = 0


class TelemetryMonthly(SQLModel, table=True):
    """Agrégation mensuelle — conservée 10 ans."""
    __tablename__ = "telemetry_monthly"
    id: Optional[int] = Field(default=None, primary_key=True)
    mois: str = Field(index=True)           # YYYY-MM
    page: str
    action: str = "view"
    utilisateurs_uniques: int = 0
    total: int = 0


class HistoriqueTelemetrie(SQLModel, table=True):
    """Historique des exécutions d'agrégation de la télémétrie."""
    __tablename__ = "historique_telemetrie"
    id: Optional[int] = Field(default=None, primary_key=True)
    declenchee_par: str = "cron"               # cron | manuelle
    #: Nœud qui a exécuté la tâche — renseigné À L'ÉCRITURE, jamais déduit à
    #: la lecture (cf. `utils/noeud.py`). Nullable et sans valeur par défaut :
    #: les lignes antérieures au 12/08/2026 resteront `None`, et c'est correct
    #: — personne ne sait sur quel nœud elles ont tourné, et l'inventer serait
    #: la faute retirée le 11/08 (#312).
    noeud: Optional[str] = Field(default=None, index=True)   # rpi1 | rpi2
    statut: str = "en_cours"                   # en_cours | succes | erreur
    jours_agreges: int = 0
    mois_agreges: int = 0
    events_purges: int = 0
    daily_purges: int = 0
    monthly_purges: int = 0
    duree_secondes: Optional[float] = None
    erreur: Optional[str] = None
    cree_le: datetime = Field(default_factory=datetime.utcnow)
    terminee_le: Optional[datetime] = None
