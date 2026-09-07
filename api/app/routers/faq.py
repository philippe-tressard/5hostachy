"""Router FAQ — lecture publique, CRUD réservé CS/Admin."""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import distinct
from sqlmodel import Session, select

from app.auth.deps import get_current_user, require_cs_or_admin
from app.database import get_session
from app.models.core import FaqItem, Utilisateur

router = APIRouter(prefix="/faq", tags=["faq"])


# ── Schémas ────────────────────────────────────────────────────────────────

class FaqItemCreate(BaseModel):
    categorie: str
    question: str
    reponse: str
    ordre: int = 0


class FaqItemUpdate(BaseModel):
    categorie: Optional[str] = None
    question: Optional[str] = None
    reponse: Optional[str] = None
    ordre: Optional[int] = None
    actif: Optional[bool] = None


class FaqReorderItem(BaseModel):
    id: int
    ordre: int


class FaqCategoryRename(BaseModel):
    old_name: str
    new_name: str


class FaqItemRead(BaseModel):
    id: int
    categorie: str
    question: str
    reponse: str
    ordre: int
    actif: bool
    cree_le: datetime
    mis_a_jour_le: datetime

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[FaqItemRead])
def list_faq(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Retourne toutes les entrées FAQ actives, triées par catégorie puis ordre."""
    return session.exec(
        select(FaqItem)
        .where(FaqItem.actif == True)
        .order_by(FaqItem.categorie, FaqItem.ordre, FaqItem.id)
    ).all()


@router.get("/categories", response_model=list[str])
def list_categories(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Retourne la liste des catégories distinctes existantes."""
    rows = session.exec(
        select(distinct(FaqItem.categorie))
        .where(FaqItem.categorie != None, FaqItem.categorie != "")
        .order_by(FaqItem.categorie)
    ).all()
    return [r for r in rows if r]


@router.patch("/categories/rename", status_code=200)
def rename_category(
    body: FaqCategoryRename,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Renomme une catégorie sur toutes les entrées FAQ correspondantes."""
    if not body.new_name.strip():
        raise HTTPException(400, "Le nouveau nom de catégorie ne peut pas être vide")
    items = session.exec(
        select(FaqItem).where(FaqItem.categorie == body.old_name)
    ).all()
    if not items:
        raise HTTPException(404, "Catégorie introuvable")
    for item in items:
        item.categorie = body.new_name.strip()
        item.mis_a_jour_le = datetime.utcnow()
        session.add(item)
    session.commit()
    return {"count": len(items), "new_name": body.new_name.strip()}


@router.get("/all", response_model=list[FaqItemRead])
def list_faq_all(
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Retourne toutes les entrées FAQ (actives + inactives), pour la gestion CS/Admin."""
    return session.exec(
        select(FaqItem).order_by(FaqItem.categorie, FaqItem.ordre, FaqItem.id)
    ).all()


@router.post("", response_model=FaqItemRead, status_code=201)
def create_faq(
    body: FaqItemCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    item = FaqItem(**body.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.patch("/reorder", status_code=204)
def reorder_faq(
    body: list[FaqReorderItem],
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    """Met à jour l'ordre d'affichage de plusieurs entrées FAQ en une seule requête."""
    for entry in body:
        item = session.get(FaqItem, entry.id)
        if item:
            item.ordre = entry.ordre
            session.add(item)
    session.commit()


@router.patch("/{item_id}", response_model=FaqItemRead)
def update_faq(
    item_id: int,
    body: FaqItemUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    item = session.get(FaqItem, item_id)
    if not item:
        raise HTTPException(404, "Entrée FAQ introuvable")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)
    item.mis_a_jour_le = datetime.utcnow()
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_faq(
    item_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(require_cs_or_admin),
):
    item = session.get(FaqItem, item_id)
    if not item:
        raise HTTPException(404, "Entrée FAQ introuvable")
    session.delete(item)
    session.commit()
