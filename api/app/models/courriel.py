"""Modèles des courriels ENTRANTS — répondre à un ticket par e-mail (#703).

Extrait de `core.py` le 03/09/2026, pour la raison écrite dans
`models/__init__.py` : ce fichier dépasse largement 500 lignes, et la règle de
modularité (rang 1) refuse qu'il grossisse pour une nouvelle fonctionnalité. Le
contrôle l'a refusé, à juste titre.

⚠️ Ce n'est pas un découpage arbitraire : la réception de courriels est un
domaine à part — `utils/courriel_entrant`, `utils/courriel_ingestion`,
`utils/courriel_boite` — et son modèle n'a pas plus sa place dans le « cœur » que
sa décision.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class RelanceCourriel(SQLModel, table=True):
    """Un envoi de relance groupée au syndic, et les tickets qu'il portait.

    🔴 La relance est un envoi **groupé** : un seul message pour N dossiers, donc
    aucun jeton de ticket — et la réponse du syndic arrivait dans la boîte sans
    rien pour la rattacher. Ignorée EN SILENCE : le seul cas où l'on perdait une
    information qu'on avait soi-même sollicitée.

    ⚠️ Elle ne se VENTILE PAS dans les fils. « Pour le TK-123 on intervient
    jeudi, le TK-456 est clos » recopié dans quatre fils serait faux dans trois
    d'entre eux ; aucune machine ne peut décider quelle phrase vise quel dossier.
    Elle va au conseil syndical, avec la liste des dossiers concernés.

    Le jeton **ne s'épuise pas** : le syndic peut répondre plusieurs fois — un
    message par dossier, une précision le lendemain —, chaque réponse retrouve la
    même relance et produit sa propre notification.

    Le pourquoi complet est dans la migration 0172.
    """

    __tablename__ = "relance_courriel"

    id: Optional[int] = Field(default=None, primary_key=True)
    #: Même forme et même tirage que `Ticket.jeton_courriel` — 128 bits, donc
    #: jamais en collision : le jeton dit à lui seul de quoi il parle, et on
    #: cherche dans les deux tables sans avoir besoin d'un préfixe distinct.
    jeton: str = Field(index=True, unique=True)
    #: Les tickets relancés, en JSON. Figée à l'envoi : elle dit ce que le
    #: message CONTENAIT, pas ce que les tickets sont devenus.
    tickets_json: str = "[]"
    cree_le: datetime = Field(default_factory=datetime.utcnow)
