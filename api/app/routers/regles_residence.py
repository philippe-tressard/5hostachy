"""Router règles & recommandations de la résidence."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import RegleResidence, Utilisateur

router = APIRouter(prefix="/regles-residence", tags=["règles résidence"])


class RegleCreate(BaseModel):
    titre: str
    contenu: str = ""


class RegleUpdate(BaseModel):
    titre: Optional[str] = None
    contenu: Optional[str] = None
    ordre: Optional[int] = None


@router.get("", response_model=list[dict])
def list_regles(
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(get_current_user),
):
    regles = session.exec(
        select(RegleResidence).order_by(RegleResidence.ordre, RegleResidence.id)
    ).all()
    return [
        {
            "id": r.id,
            "titre": r.titre,
            "contenu": r.contenu,
            "ordre": r.ordre,
            "cree_par_id": r.cree_par_id,
            "cree_le": r.cree_le.isoformat() if r.cree_le else None,
            "modifie_le": r.modifie_le.isoformat() if r.modifie_le else None,
        }
        for r in regles
    ]


@router.post("", status_code=201)
def create_regle(
    body: RegleCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    regle = RegleResidence(
        titre=body.titre,
        contenu=body.contenu,
        cree_par_id=user.id,
        cree_le=datetime.utcnow(),
    )
    session.add(regle)
    session.commit()
    session.refresh(regle)
    return {"id": regle.id, "titre": regle.titre, "contenu": regle.contenu, "ordre": regle.ordre}


@router.patch("/{regle_id}")
def update_regle(
    regle_id: int,
    body: RegleUpdate,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    regle = session.get(RegleResidence, regle_id)
    if not regle:
        raise HTTPException(404, "Règle introuvable")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(regle, k, v)
    regle.modifie_le = datetime.utcnow()
    session.add(regle)
    session.commit()
    session.refresh(regle)
    return {"id": regle.id, "titre": regle.titre, "contenu": regle.contenu, "ordre": regle.ordre}


@router.delete("/{regle_id}", status_code=204)
def delete_regle(
    regle_id: int,
    session: Session = Depends(get_session),
    _: Utilisateur = Depends(require_cs_or_admin),
):
    regle = session.get(RegleResidence, regle_id)
    if not regle:
        raise HTTPException(404, "Règle introuvable")
    session.delete(regle)
    session.commit()
