"""Router petites annonces — communauté résidence."""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import (
    PetiteAnnonce, TypeAnnonce, CategorieAnnonce, StatutAnnonce,
    Utilisateur, StatutUtilisateur, RoleUtilisateur,
)
from app.routers.uploads import _save_image

router = APIRouter(prefix="/annonces", tags=["annonces"])

MAX_PHOTOS = 5


def _deny_communaute_for_statut(user: Utilisateur) -> None:
    if user.statut in (StatutUtilisateur.syndic, StatutUtilisateur.mandataire):
        raise HTTPException(403, "La rubrique Communauté n'est pas accessible à votre profil")
    if user.communaute_interdit:
        raise HTTPException(403, "Votre accès à la Communauté a été définitivement suspendu.")
    if user.communaute_ban_jusqu_au and user.communaute_ban_jusqu_au > datetime.utcnow():
        raise HTTPException(403, "Votre accès à la Communauté est suspendu pour une période probatoire d\u2019un mois. À la 2\u1d49 infraction, vous serez banni définitivement.")


def _can_manage(annonce: PetiteAnnonce, user: Utilisateur) -> bool:
    """Auteur, CS ou admin peut modifier/supprimer."""
    return (
        annonce.auteur_id == user.id
        or user.role in (RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
    )


def _enrich(annonce: PetiteAnnonce, user: Utilisateur, session: Session) -> dict:
    auteur = session.get(Utilisateur, annonce.auteur_id)
    return {
        **annonce.model_dump(),
        "photos": json.loads(annonce.photos_json),
        "auteur_prenom": auteur.prenom if auteur else "",
        "auteur_nom": auteur.nom if auteur else "",
        "auteur_email": auteur.email if annonce.contact_visible and auteur else None,
        "est_auteur": annonce.auteur_id == user.id,
    }


# ── Schémas ────────────────────────────────────────────────────────────────

class AnnonceCreate(BaseModel):
    titre: str
    description: str
    type_annonce: TypeAnnonce = TypeAnnonce.vente
    categorie: CategorieAnnonce = CategorieAnnonce.divers
    prix: Optional[float] = None
    negotiable: bool = False
    contact_visible: bool = True


class AnnonceUpdate(BaseModel):
    titre: Optional[str] = None
    description: Optional[str] = None
    type_annonce: Optional[TypeAnnonce] = None
    categorie: Optional[CategorieAnnonce] = None
    prix: Optional[float] = None
    negotiable: Optional[bool] = None
    contact_visible: Optional[bool] = None


class AnnonceStatutUpdate(BaseModel):
    statut: StatutAnnonce


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("")
def list_annonces(
    type_annonce: Optional[str] = None,
    categorie: Optional[str] = None,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    stmt = (
        select(PetiteAnnonce)
        .where(PetiteAnnonce.statut != StatutAnnonce.archive)
        .order_by(PetiteAnnonce.cree_le.desc())  # type: ignore[arg-type]
    )
    annonces = session.exec(stmt).all()
    if type_annonce:
        annonces = [a for a in annonces if a.type_annonce == type_annonce]
    if categorie:
        annonces = [a for a in annonces if a.categorie == categorie]
    return [_enrich(a, user, session) for a in annonces]


@router.post("")
def create_annonce(
    data: AnnonceCreate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    annonce = PetiteAnnonce(
        titre=data.titre,
        description=data.description,
        type_annonce=data.type_annonce,
        categorie=data.categorie,
        prix=data.prix,
        negotiable=data.negotiable,
        contact_visible=data.contact_visible,
        auteur_id=user.id,
    )
    session.add(annonce)
    session.commit()
    session.refresh(annonce)
    return _enrich(annonce, user, session)


@router.patch("/{annonce_id}")
def update_annonce(
    annonce_id: int,
    data: AnnonceUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    annonce = session.get(PetiteAnnonce, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    if not _can_manage(annonce, user):
        raise HTTPException(403, "Non autorisé")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(annonce, field, value)
    annonce.mis_a_jour_le = datetime.utcnow()
    session.add(annonce)
    session.commit()
    session.refresh(annonce)
    return _enrich(annonce, user, session)


@router.patch("/{annonce_id}/statut")
def update_statut(
    annonce_id: int,
    data: AnnonceStatutUpdate,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    annonce = session.get(PetiteAnnonce, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    if not _can_manage(annonce, user):
        raise HTTPException(403, "Non autorisé")
    annonce.statut = data.statut
    annonce.mis_a_jour_le = datetime.utcnow()
    session.add(annonce)
    session.commit()
    return {"ok": True}


@router.delete("/{annonce_id}")
def delete_annonce(
    annonce_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    annonce = session.get(PetiteAnnonce, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    if not _can_manage(annonce, user):
        raise HTTPException(403, "Non autorisé")
    session.delete(annonce)
    session.commit()
    return {"ok": True}


@router.post("/{annonce_id}/photo")
def add_photo(
    annonce_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    annonce = session.get(PetiteAnnonce, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    if annonce.auteur_id != user.id:
        raise HTTPException(403, "Seul l'auteur peut ajouter des photos")
    photos = json.loads(annonce.photos_json)
    if len(photos) >= MAX_PHOTOS:
        raise HTTPException(400, f"Maximum {MAX_PHOTOS} photos par annonce")
    url = _save_image(file, "annonces", max_dim=1200)
    photos.append(url)
    annonce.photos_json = json.dumps(photos)
    annonce.mis_a_jour_le = datetime.utcnow()
    session.add(annonce)
    session.commit()
    return {"url": url, "photos": photos}


@router.delete("/{annonce_id}/photo")
def remove_photo(
    annonce_id: int,
    url: str,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    annonce = session.get(PetiteAnnonce, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    if annonce.auteur_id != user.id:
        raise HTTPException(403, "Seul l'auteur peut supprimer ses photos")
    photos = [p for p in json.loads(annonce.photos_json) if p != url]
    annonce.photos_json = json.dumps(photos)
    annonce.mis_a_jour_le = datetime.utcnow()
    session.add(annonce)
    session.commit()
    return {"photos": photos}
