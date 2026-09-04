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


class ReponseRelance(SQLModel, table=True):
    """Une réponse du syndic à une relance groupée — CONSERVÉE, pas seulement notifiée.

    🔴 POURQUOI CETTE TABLE EXISTE (04/09/2026), et c'est une correction.

    La première version se contentait d'une notification portant le texte. Elle
    répondait à « le conseil est-il prévenu ? » et pas à « où le relit-on ? ».
    Une notification se lit une fois puis descend dans la pile ; passé quelques
    jours, la réponse du syndic était en base — dans un champ `corps` — et
    introuvable.

    ⚠️ C'est le défaut même que tout ce lot prétendait corriger : *« une réponse
    arrive et personne ne la voit »*. Je l'avais déplacé de la boîte aux lettres
    vers une table de notifications, ce qui n'est pas la même chose que le
    résoudre. Relevé à l'écran : *« où sera affiché le retour syndic ? »*.

    Elle s'affiche désormais sous la relance qui l'a provoquée — Espace CS →
    Reporting → Relance syndic —, là où le conseil regarde déjà.

    ⚠️ Plusieurs réponses par relance : le jeton ne s'épuise pas. Le syndic peut
    répondre un dossier à la fois, ou préciser le lendemain. Chaque réponse est
    une ligne, jamais un écrasement de la précédente.
    """

    __tablename__ = "reponse_relance"

    id: Optional[int] = Field(default=None, primary_key=True)
    relance_id: int = Field(index=True)
    #: L'adresse telle qu'elle figurait dans le `From:` — après quoi
    #: l'authentification a été vérifiée. On conserve la forme brute : c'est ce
    #: qu'un humain reconnaît, et le nom affiché fait partie de l'information.
    expediteur: str = ""
    #: Le texte SANS la citation du message précédent : sans quoi chaque échange
    #: recopierait tout l'échange.
    contenu: str = ""
    recue_le: datetime = Field(default_factory=datetime.utcnow)
