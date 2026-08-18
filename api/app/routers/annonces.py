"""Router petites annonces — communauté résidence."""
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.database import get_session
from app.models.core import (
    PetiteAnnonce, TypeAnnonce, CategorieAnnonce, StatutAnnonce,
    ReponseCommunaute, Utilisateur, StatutUtilisateur, RoleUtilisateur,
)
from app.routers.uploads import _save_image
from app.utils.liens import lien_element
from app.utils.reponses import (
    auteur_meta, enrich_reponse, notifier_nouvelle_reponse, tri_reponses,
)

router = APIRouter(prefix="/annonces", tags=["annonces"])

MAX_PHOTOS = 5
RUBRIQUE = "annonce"


def _reponses_for(annonce_id: int, session: Session) -> list[dict]:
    """Réponses d'une annonce : CS/admin en tête (plus de poids), puis chronologique."""
    reps = session.exec(
        select(ReponseCommunaute).where(
            ReponseCommunaute.rubrique == RUBRIQUE,
            ReponseCommunaute.cible_id == annonce_id,
        )
    ).all()
    return tri_reponses([enrich_reponse(r, session) for r in reps])


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
        or user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
    )


def _enrich(annonce: PetiteAnnonce, user: Utilisateur, session: Session) -> dict:
    auteur = session.get(Utilisateur, annonce.auteur_id)
    reponses = _reponses_for(annonce.id, session)
    return {
        **annonce.model_dump(),
        "photos": json.loads(annonce.photos_json),
        #  Le périmètre sort en LISTE de codes, jamais en JSON brut : c'est ce que
        #  `PerimetrePicker` et `perimetreLabel` lisent côté front. Le `or` couvre les
        #  annonces déposées AVANT la migration 0151 — elles valaient « résidence » de
        #  fait, elles le valent explicitement.
        "perimetre_cible": json.loads(annonce.perimetre_cible or '["résidence"]'),
        "auteur_prenom": auteur.prenom if auteur else "",
        "auteur_nom": auteur.nom if auteur else "",
        "auteur_email": auteur.email if annonce.contact_visible and auteur else None,
        "est_auteur": annonce.auteur_id == user.id,
        "reponses": reponses,
        "nb_reponses": len(reponses),
    }


# ── Schémas ────────────────────────────────────────────────────────────────

class AnnonceCreate(BaseModel):
    titre: str
    description: str
    #  Section 4 du cadre #430. Reçu en LISTE, stocké en JSON — même contrat que
    #  `PublicationCreate` : la conversion se fait ici, à la frontière, et une
    #  seule fois.
    perimetre_cible: List[str] = ["résidence"]
    type_annonce: TypeAnnonce = TypeAnnonce.vente
    categorie: CategorieAnnonce = CategorieAnnonce.divers
    prix: Optional[float] = None
    negotiable: bool = False
    contact_visible: bool = True


class AnnonceUpdate(BaseModel):
    titre: Optional[str] = None
    perimetre_cible: Optional[List[str]] = None
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
        perimetre_cible=json.dumps(data.perimetre_cible, ensure_ascii=False),
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
    maj = data.model_dump(exclude_none=True)
    #  ⚠️ Le périmètre arrive en LISTE et la colonne est du TEXTE : sans cette
    #  conversion, SQLite stockerait la repr Python d'une liste — que `json.loads`
    #  ne relit pas, et l'annonce perdrait son périmètre à la première correction.
    if "perimetre_cible" in maj:
        maj["perimetre_cible"] = json.dumps(maj["perimetre_cible"], ensure_ascii=False)
    for field, value in maj.items():
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
    # Réponses associées supprimées en cascade
    reps = session.exec(
        select(ReponseCommunaute).where(
            ReponseCommunaute.rubrique == RUBRIQUE,
            ReponseCommunaute.cible_id == annonce_id,
        )
    ).all()
    for r in reps:
        session.delete(r)
    session.delete(annonce)
    session.commit()
    return {"ok": True}


# ── Réponses aux annonces ────────────────────────────────────────────────────

class ReponseCreate(BaseModel):
    contenu: str


@router.get("/{annonce_id}/reponses")
def list_reponses(
    annonce_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    annonce = session.get(PetiteAnnonce, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    return _reponses_for(annonce_id, session)


@router.post("/{annonce_id}/reponses", status_code=201)
def create_reponse(
    annonce_id: int,
    body: ReponseCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    _deny_communaute_for_statut(user)
    if user.has_role(RoleUtilisateur.externe) and not user.has_role(
        RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin
    ):
        raise HTTPException(403, "Les utilisateurs externes ne peuvent pas répondre")
    contenu = (body.contenu or "").strip()
    if not contenu:
        raise HTTPException(422, "La réponse ne peut pas être vide")
    annonce = session.get(PetiteAnnonce, annonce_id)
    if not annonce:
        raise HTTPException(404, "Annonce introuvable")
    rep = ReponseCommunaute(rubrique=RUBRIQUE, cible_id=annonce_id, auteur_id=user.id, contenu=contenu)
    session.add(rep)
    notifier_nouvelle_reponse(
        session, background_tasks,
        createur_id=annonce.auteur_id, auteur=user,
        rubrique_label="votre annonce", sujet=annonce.titre,
        extrait=contenu, lien_path=lien_element("annonce", annonce_id),
    )
    session.commit()
    session.refresh(rep)
    return {"id": rep.id, "cible_id": rep.cible_id, "auteur_id": rep.auteur_id,
            "contenu": rep.contenu, "cree_le": rep.cree_le, **auteur_meta(user, session)}


@router.delete("/{annonce_id}/reponses/{rep_id}", status_code=204)
def delete_reponse(
    annonce_id: int,
    rep_id: int,
    session: Session = Depends(get_session),
    user: Utilisateur = Depends(get_current_user),
):
    """Supprimer une réponse : son auteur, ou un CS/admin."""
    _deny_communaute_for_statut(user)
    rep = session.get(ReponseCommunaute, rep_id)
    if not rep or rep.rubrique != RUBRIQUE or rep.cible_id != annonce_id:
        raise HTTPException(404, "Réponse introuvable")
    est_cs = user.has_role(RoleUtilisateur.conseil_syndical, RoleUtilisateur.admin)
    if rep.auteur_id != user.id and not est_cs:
        raise HTTPException(403, "Vous ne pouvez supprimer que vos propres réponses")
    session.delete(rep)
    session.commit()


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
