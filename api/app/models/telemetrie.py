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

from app.utils import horloge
from typing import Optional

from sqlmodel import Field, SQLModel
from pydantic import NaiveDatetime

# ──────────────────────────────────────────────
#  Télémétrie
# ──────────────────────────────────────────────


class TelemetryEvent(SQLModel, table=True):
    """Événement brut de télémétrie — conservé 30 jours puis agrégé.

    ⚠️ `user_id` a été retirée par la 0246 (#1545) puis RÉTABLIE par la 0247 le
    même jour : son retrait supprimait les statistiques par utilisateur sans
    l'accord de l'utilisateur du produit. Elle revient en colonne simple, SANS
    clé étrangère — SQLite refuse d'en ajouter une à une table existante, et
    déclarer `foreign_key` ici ferait diverger base neuve et base migrée.
    """

    __tablename__ = "telemetry_event"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = None
    page: str = Field(index=True)  # ex: /actualites, /tickets
    action: str = "view"  # view | click | submit
    detail: Optional[str] = None  # ex: bouton cliqué, id ticket
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant, index=True)


class TelemetryDaily(SQLModel, table=True):
    """Agrégation journalière — conservée 12 mois."""

    __tablename__ = "telemetry_daily"
    id: Optional[int] = Field(default=None, primary_key=True)
    jour: str = Field(index=True)  # YYYY-MM-DD
    page: str
    action: str = "view"
    utilisateurs_uniques: int = 0
    total: int = 0


class TelemetryMonthly(SQLModel, table=True):
    """Agrégation mensuelle — conservée 10 ans."""

    __tablename__ = "telemetry_monthly"
    id: Optional[int] = Field(default=None, primary_key=True)
    mois: str = Field(index=True)  # YYYY-MM
    page: str
    action: str = "view"
    utilisateurs_uniques: int = 0
    total: int = 0


class ErreurNavigateur(SQLModel, table=True):
    """Une erreur vue par les résidents, COMPTÉE par jour, page et code (#1631).

    Pas un événement : un compteur, et SANS `user_id` — savoir qu'un écran casse
    ne demande pas de savoir chez qui. Écrit et lu par `utils/erreurs_navigateur`,
    purgé après `CONSERVATION_JOURS` par l'agrégation quotidienne.
    """

    __tablename__ = "erreur_navigateur"
    id: Optional[int] = Field(default=None, primary_key=True)
    jour: str = Field(index=True)  # YYYY-MM-DD, jour de Paris
    page: str
    code: str  # produit par `codeErreur` (front/src/lib/telemetry.ts)
    total: int = 0
    premiere_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    derniere_le: NaiveDatetime = Field(default_factory=horloge.maintenant)


class HistoriqueTelemetrie(SQLModel, table=True):
    """Historique des exécutions d'agrégation de la télémétrie."""

    __tablename__ = "historique_telemetrie"
    id: Optional[int] = Field(default=None, primary_key=True)
    declenchee_par: str = "cron"  # cron | manuelle
    #: Nœud qui a exécuté la tâche — renseigné À L'ÉCRITURE, jamais déduit à
    #: la lecture (cf. `utils/noeud.py`). Nullable et sans valeur par défaut :
    #: les lignes antérieures au 12/08/2026 resteront `None`, et c'est correct
    #: — personne ne sait sur quel nœud elles ont tourné, et l'inventer serait
    #: la faute retirée le 11/08 (#312).
    noeud: Optional[str] = Field(default=None, index=True)  # rpi1 | rpi2
    statut: str = "en_cours"  # en_cours | succes | erreur
    jours_agreges: int = 0
    mois_agreges: int = 0
    events_purges: int = 0
    daily_purges: int = 0
    monthly_purges: int = 0
    duree_secondes: Optional[float] = None
    erreur: Optional[str] = None
    cree_le: NaiveDatetime = Field(default_factory=horloge.maintenant)
    terminee_le: Optional[NaiveDatetime] = None
