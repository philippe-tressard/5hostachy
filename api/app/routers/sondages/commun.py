"""Schémas partagés et garde d'accès à la rubrique Communauté.

Extrait de `sondages.py` le 17/08/2026 lors du découpage (cf. `__init__.py`).
Ce module ne porte AUCUN endpoint : il est importé par `crud` et par
`participation`, qui en dépendent tous les deux.
"""
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel

from app.models.core import StatutUtilisateur, Utilisateur
from app.schemas import ListeJson


# ── helpers ──────────────────────────────────────────────────────────────────

def _deny_communaute_for_statut(user: Utilisateur) -> None:
    if user.statut in (StatutUtilisateur.syndic, StatutUtilisateur.mandataire):
        raise HTTPException(403, "La rubrique Communauté n'est pas accessible à votre profil")
    if user.communaute_interdit:
        raise HTTPException(403, "Votre accès à la Communauté a été définitivement suspendu.")
    if user.communaute_ban_jusqu_au and user.communaute_ban_jusqu_au > datetime.utcnow():
        raise HTTPException(403, "Votre accès à la Communauté est suspendu pour une période probatoire d\u2019un mois. À la 2\u1d49 infraction, vous serez banni définitivement.")


# ── schémas ──────────────────────────────────────────────────────────────────

class OptionCreate(BaseModel):
    libelle: str
    ordre: int = 0
    champ_libre: bool = False


class SondageCreate(BaseModel):
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    resultats_publics: bool = True
    options: list[OptionCreate]
    #  MÊMES deux champs que les publications : codes de périmètre et codes de
    #  public. `None`/vide = aucune restriction, des deux côtés.
    perimetre_cible: Optional[List[str]] = None
    public_cible: Optional[List[str]] = None
    partager_whatsapp: bool = False
    envoyer_syndic: bool = False
    envoyer_cs: bool = False


class SondageRead(BaseModel):
    id: int
    question: str
    description: Optional[str] = None
    cloture_le: Optional[datetime] = None
    cloture_forcee: bool = False
    resultats_publics: bool
    auteur_id: int
    cree_le: datetime
    #  Exposés en LISTES, comme les publications et les tickets : la colonne est
    #  du texte JSON, mais aucun appelant ne doit avoir à le savoir. La page des
    #  sondages découpait la chaîne à la main et affichait les codes bruts.
    perimetre_cible: ListeJson = []
    public_cible: ListeJson = []
    nb_votants: int = 0
    #  « Ce sondage est-il terminé ? » — répondu par le SERVEUR, via l'unique
    #  `sondage_clos()`, et transporté. Il n'était exposé que sur la fiche : la
    #  liste n'avait donc pas le choix, elle recalculait la règle en JavaScript
    #  (`estCloture`). Deux implémentations d'une même question, dont une seule
    #  fait autorité — et elles divergeaient déjà sur le fuseau, le front
    #  comparant à l'heure LOCALE du navigateur quand le serveur date en UTC
    #  (#468). Un écran ne tranche pas ce genre de question (`ux-patterns` §16).
    cloture: bool = False

    class Config:
        from_attributes = True


class OptionRead(BaseModel):
    id: int
    libelle: str
    ordre: int
    nb_votes: int = 0
    champ_libre: bool = False

    class Config:
        from_attributes = True


class SondageDetail(SondageRead):
    options: list[OptionRead] = []
    mon_vote: Optional[int] = None
    #  `cloture` est HÉRITÉ de `SondageRead` depuis le 19/08/2026 — il y était
    #  déclaré deux fois.

