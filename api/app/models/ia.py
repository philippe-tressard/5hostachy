"""Le JOURNAL des appels à l'assistant IA — ce qui a été demandé, et ce que ça a coûté.

Né le 27/09/2026 (#1383). L'assistant a trois usages, dont un AUTOMATIQUE : la
mise en forme des réponses du syndic reçues par courriel, relevées toutes les
dix minutes (#1322). Aucun appel n'était compté — ni jetons, ni coût, ni
plafond. Une boucle (un courriel qui en déclenche un autre) aurait facturé en
silence, et le gestionnaire ne savait pas ce que coûte chaque usage.

🔴 **Des compteurs, jamais du contenu.** Ni la consigne, ni le message, ni la
réponse : ils portent des contrats, des courriels du syndic, des descriptions
de résidents. Rien ici ne permet de retrouver QUI a demandé QUOI
(`standards/14`) ; le journal répond à « combien », pas à « quoi ».

L'écriture et la lecture vivent dans `utils/llm_journal.py`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.utils import horloge


class AppelIA(SQLModel, table=True):
    __tablename__ = "appel_ia"

    id: Optional[int] = Field(default=None, primary_key=True)
    cree_le: datetime = Field(default_factory=horloge.maintenant, index=True)
    #: Le code de l'usage (`llm_usages.USAGES`).
    usage: str = Field(index=True)
    fournisseur: str
    modele: str
    #: Lus dans la réponse du fournisseur ; `None` quand il ne les donne pas —
    #: jamais 0, qui se lirait « gratuit ».
    jetons_entree: Optional[int] = None
    jetons_sortie: Optional[int] = None
    duree_ms: int = 0
    #: `succes` · `erreur` (le fournisseur a répondu en échec) · `plafond`
    #: (refusé AVANT l'envoi : le plafond mensuel de l'usage est atteint).
    statut: str = "succes"
