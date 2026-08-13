"""Router copropriété — fiche, bâtiments, lots."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_admin
from app.database import get_session
from app.models.core import Batiment, Copropriete, Lot, Utilisateur

router = APIRouter(prefix="/copropriete", tags=["copropriété"])


class CoproprieteUpdate(BaseModel):
    nom: Optional[str] = None
    adresse: Optional[str] = None
    annee_construction: Optional[int] = None
    nb_lots_total: Optional[int] = None
    nb_lots_principaux: Optional[int] = None
    nb_parkings_communs: Optional[int] = None
    numero_immatriculation: Optional[str] = None
    assurance_compagnie: Optional[str] = None
    assurance_numero_police: Optional[str] = None
    assurance_echeance: Optional[str] = None  # date string ISO


class CoproprieteRead(BaseModel):
    id: int
    nom: str
    adresse: str
    annee_construction: Optional[int] = None
    nb_lots_total: Optional[int] = None
    nb_lots_principaux: Optional[int] = None
    numero_immatriculation: Optional[str] = None
    assurance_compagnie: Optional[str] = None
    assurance_numero_police: Optional[str] = None
    assurance_echeance: Optional[date] = None
    photo_url: Optional[str] = None
    nb_parkings_communs: int = 0

    class Config:
        from_attributes = True


class BatimentRead(BaseModel):
    id: int
    numero: str
    nb_etages: int
    specificites: Optional[str] = None
    nb_appartements: int = 0
    nb_caves: int = 0
    nb_parkings: int = 0
    nb_locaux_commerciaux: int = 0

    class Config:
        from_attributes = True


class LotRead(BaseModel):
    id: int
    batiment_id: Optional[int] = None  # None pour les parkings
    batiment_nom: Optional[str] = None  # enrichi à la sérialisation
    numero: str
    type: str
    type_appartement: Optional[str] = None
    etage: Optional[int] = None

    class Config:
        from_attributes = True


@router.get("", response_model=CoproprieteRead)
def get_copropriete(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    copro = session.exec(select(Copropriete)).first()
    if not copro:
        raise HTTPException(404, "Copropriété non configurée")
    return copro


@router.patch("", response_model=CoproprieteRead)
def update_copropriete(
    body: CoproprieteUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_admin),
):
    copro = session.exec(select(Copropriete)).first()
    if not copro:
        raise HTTPException(404, "Copropriété non configurée")
    donnees = body.model_dump(exclude_none=True)

    #  `assurance_echeance` arrive en CHAÎNE (« 2026-12-17 ») et la colonne est un
    #  `date` : affecter la chaîne telle quelle faisait lever SQLAlchemy —
    #  « SQLite Date type only accepts Python date objects as input » — et TOUTE
    #  la fiche devenait inenregistrable, y compris quand on n'avait modifié que
    #  le nom du syndic. Signalé à l'usage le 13/08/2026 ; le défaut existait
    #  depuis que le champ avait été ajouté, personne n'ayant retouché l'échéance.
    echeance = donnees.get("assurance_echeance")
    if echeance is not None:
        if isinstance(echeance, str) and not echeance.strip():
            donnees["assurance_echeance"] = None      # champ vidé
        elif isinstance(echeance, str):
            try:
                donnees["assurance_echeance"] = date.fromisoformat(echeance.strip()[:10])
            except ValueError:
                raise HTTPException(
                    422, f"Échéance d'assurance illisible : « {echeance} » "
                         "(format attendu : AAAA-MM-JJ)."
                )

    for k, v in donnees.items():
        setattr(copro, k, v)
    session.add(copro)
    session.commit()
    session.refresh(copro)
    return copro


@router.get("/batiments", response_model=list[BatimentRead])
def get_batiments(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    return session.exec(select(Batiment)).all()


@router.get("/lots")
def get_lots(
    batiment_id: Optional[int] = None,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    stmt = select(Lot)
    if batiment_id:
        stmt = stmt.where(Lot.batiment_id == batiment_id)
    lots = session.exec(stmt).all()
    result = []
    for lot in lots:
        bat = session.get(Batiment, lot.batiment_id) if lot.batiment_id else None
        d = LotRead.model_validate(lot)
        d.batiment_nom = bat.numero if bat else None
        result.append(d)
    return result
