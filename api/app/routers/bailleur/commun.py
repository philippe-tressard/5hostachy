"""Ce que les quatre modules du bailleur partagent : l'accès à un bail, et les
schémas d'entrée/sortie.

🔴 `_get_bail_or_404` est la RÈGLE D'AUTORISATION de ce domaine — « ce bail est
le vôtre, ou vous êtes admin/CS ». Elle vit ici et **nulle part ailleurs** : une
règle d'autorisation écrite deux fois se durcit une fois sur deux, et ce dépôt a
déjà payé ce prix avec `_require_bailleur` (17 endpoints sur un doublon posé hors
du module central).
"""
from datetime import date, datetime
from typing import List, Optional

from fastapi import HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.models.core import (
    LocationBail, StatutBail, StatutObjet, TypeObjet,
    Utilisateur, RoleUtilisateur,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_bail_or_404(bail_id: int, user: Utilisateur, session: Session) -> LocationBail:
    bail = session.get(LocationBail, bail_id)
    if not bail:
        raise HTTPException(status_code=404, detail="Bail introuvable")
    if bail.bailleur_id != user.id and not user.has_role(
        RoleUtilisateur.admin, RoleUtilisateur.conseil_syndical
    ):
        raise HTTPException(status_code=403, detail="Accès interdit")
    return bail


# ── Schemas in / out ─────────────────────────────────────────────────────────

class ObjetOut(BaseModel):
    id: int
    bail_id: int
    type: TypeObjet
    libelle: str
    quantite: int
    reference: Optional[str]
    statut: StatutObjet
    remis_le: Optional[date]
    rendu_le: Optional[date]
    notes: Optional[str]
    cree_le: datetime

    class Config:
        from_attributes = True


class BailOut(BaseModel):
    id: int
    lot_id: int
    bailleur_id: int
    locataire_id: Optional[int]
    locataire_nom: Optional[str]
    locataire_prenom: Optional[str]
    locataire_email: Optional[str]
    locataire_telephone: Optional[str]
    date_entree: date
    date_sortie_prevue: Optional[date]
    date_sortie_reelle: Optional[date]
    statut: StatutBail
    notes: Optional[str]
    cree_le: datetime
    mis_a_jour_le: datetime
    objets: List[ObjetOut] = []

    class Config:
        from_attributes = True


class BailCreate(BaseModel):
    lot_id: int
    locataire_id: Optional[int] = None
    locataire_nom: Optional[str] = None
    locataire_prenom: Optional[str] = None
    locataire_email: Optional[str] = None
    locataire_telephone: Optional[str] = None
    date_entree: date
    date_sortie_prevue: Optional[date] = None
    notes: Optional[str] = None


class BailCreateMulti(BaseModel):
    """Création d'un bail sur plusieurs lots simultanément (un LocationBail par lot)."""
    lot_ids: List[int]
    locataire_id: Optional[int] = None
    locataire_nom: Optional[str] = None
    locataire_prenom: Optional[str] = None
    locataire_email: Optional[str] = None
    locataire_telephone: Optional[str] = None
    date_entree: date
    date_sortie_prevue: Optional[date] = None
    notes: Optional[str] = None


class BailUpdate(BaseModel):
    locataire_id: Optional[int] = None
    locataire_nom: Optional[str] = None
    locataire_prenom: Optional[str] = None
    locataire_email: Optional[str] = None
    locataire_telephone: Optional[str] = None
    date_sortie_prevue: Optional[date] = None
    notes: Optional[str] = None


class BailTerminer(BaseModel):
    date_sortie_reelle: Optional[date] = None


class ObjetCreate(BaseModel):
    type: TypeObjet = TypeObjet.autre
    libelle: str
    quantite: int = 1
    reference: Optional[str] = None
    remis_le: Optional[date] = None
    notes: Optional[str] = None


class ObjetUpdate(BaseModel):
    #  🔴 `type` et `remis_le` AJOUTÉS le 06/09/2026 (#806). Sans eux, corriger
    #  une saisie n'était possible qu'à moitié : un objet enregistré « Clé » alors
    #  que c'était un Vigik, ou remis à la mauvaise date, imposait de le supprimer
    #  et de le ressaisir — donc de perdre sa ligne d'inventaire.
    #
    #  ⚠️ C'est ce qui permet au formulaire de correction d'être EXACTEMENT celui
    #  de la création. Un schéma plus pauvre que son jumeau force l'écran à
    #  diverger, et la divergence se déclare ensuite comme une dette (`api`, R4 du
    #  cadre d'interface) — autant ne pas la créer.
    type: Optional[TypeObjet] = None
    libelle: Optional[str] = None
    quantite: Optional[int] = None
    reference: Optional[str] = None
    remis_le: Optional[date] = None
    notes: Optional[str] = None

    #  ⚠️ Ce qui reste HORS de ce schéma, et c'est délibéré : `statut` et
    #  `rendu_le`. Un retour se prononce par `POST …/retour`, qui pose les deux
    #  ensemble. Les ouvrir ici donnerait deux chemins pour le même fait — dont un
    #  capable de dire « rendu » sans date, ou une date sans le statut.


class RetourObjet(BaseModel):
    rendu_le: Optional[date] = None
    perdu: bool = False
